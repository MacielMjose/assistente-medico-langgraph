"""Testes de ingestão de embeddings e busca vetorial via LangChain (PGVector)."""

from pathlib import Path

import pytest

from database.embeddings_ingest import rodar_ingestao
from database.etl_seed import rodar_etl
from src.db.buscar import BuscaRepositorio
from src.db.connection import conectar
from src.db.embeddings import dividir_documento, dividir_em_chunks, obter_provedor
from src.db.vectorstore import estatisticas_chunks

RAIZ = Path(__file__).resolve().parents[1]
PARQUET = RAIZ / "database" / "dataset_medpt_curado.parquet"

pytestmark = pytest.mark.pg

N_PACIENTES = 50
LIMITE_ETL = 1_000
LIMITE_INGEST = 1_000


@pytest.fixture(scope="module")
def mini_db(dsn_teste) -> str:
    rodar_etl(
        caminho_parquet=PARQUET,
        dsn=dsn_teste,
        n_pacientes=N_PACIENTES,
        limite_linhas=LIMITE_ETL,
    )
    return dsn_teste


def test_dividir_em_chunks_texto_curto():
    texto = "Paciente relata dor lombar há duas semanas."
    assert dividir_em_chunks(texto, max_chars=600) == [texto]


def test_dividir_em_chunks_nao_corta_palavra():
    texto = ("palavra " * 500).strip()
    chunks = dividir_em_chunks(texto, max_chars=600)
    assert len(chunks) > 1
    assert all(len(c) <= 600 for c in chunks)
    assert all(not c.startswith(" ") and not c.endswith(" ") for c in chunks)
    assert all(c.split() for c in chunks)


def test_dividir_em_chunks_normaliza_espacos():
    texto = "linha um\n\nlinha   dois\t\ttres"
    chunks = dividir_em_chunks(texto, max_chars=600)
    assert chunks == ["linha um linha dois tres"]


def test_dividir_em_chunks_pequeno_respeita_limite_e_normaliza():
    chunks = dividir_em_chunks("linha um\n\nlinha dois", max_chars=10)
    assert chunks
    assert all(len(c) <= 10 for c in chunks)
    assert all("\n" not in c and "\t" not in c and "  " not in c for c in chunks)


def test_dividir_documento_preserva_metadados_e_ordem():
    from langchain_core.documents import Document

    documento = Document(
        page_content=("queixa inicial\n" * 500).strip(),
        metadata={"atendimento_id": 42, "paciente_id": 7, "condicao": "Migrânea"},
    )
    chunks = dividir_documento(documento, max_chars=600)
    assert len(chunks) > 1
    for ordem, pedaco in enumerate(chunks):
        assert pedaco.metadata["atendimento_id"] == 42
        assert pedaco.metadata["paciente_id"] == 7
        assert pedaco.metadata["condicao"] == "Migrânea"
        assert pedaco.metadata["ordem_chunk"] == ordem
        assert len(pedaco.page_content) <= 600
    assert chunks[0].page_content.startswith("queixa inicial")
    assert all("\n" not in c.page_content and "  " not in c.page_content for c in chunks)


def test_provedor_desconhecido():
    with pytest.raises(ValueError):
        obter_provedor("nao-existe")


def test_mock_processo_deterministico():
    provedor = obter_provedor("mock")
    v1, v2 = provedor.embed_documents(["mesmo texto", "mesmo texto"])
    assert v1 == v2
    assert provedor.embed_query("consulta") != []


@pytest.fixture(scope="module")
def mini_db_com_embeddings(mini_db: str) -> str:
    resumo = rodar_ingestao(provedor_nome="mock", dsn=mini_db, limite=LIMITE_INGEST)
    assert resumo["atendimentos"] == LIMITE_INGEST
    assert resumo["chunks"] >= LIMITE_INGEST
    return mini_db


def test_busca_vetorial_retorna_top_k_ordenado(mini_db_com_embeddings: str):
    provedor = obter_provedor("mock")
    resultados = BuscaRepositorio(mini_db_com_embeddings).buscar_vetorial(
        "dor de cabeça", provedor, k=5
    )
    assert 0 < len(resultados) <= 5
    similaridades = [r.similaridade for r in resultados]
    assert similaridades == sorted(similaridades, reverse=True)
    for r in resultados:
        assert r.atendimento_id > 0
        assert r.condicao
        assert r.especialidade_principal
        assert r.conteudo


def test_busca_vetorial_consulta_exata_apresenta_similaridade_maxima(mini_db_com_embeddings: str):
    with conectar(mini_db_com_embeddings) as con:
        trecho = con.execute(
            """
            SELECT e.document
            FROM langchain_pg_embedding e
            JOIN langchain_pg_collection c ON c.uuid = e.collection_id
            WHERE length(e.document) > 30
            LIMIT 1
            """
        ).fetchone()["document"]
    assert trecho

    provedor = obter_provedor("mock")
    resultados = BuscaRepositorio(mini_db_com_embeddings).buscar_vetorial(
        trecho, provedor, k=3
    )
    assert resultados[0].similaridade > 0.9999
    assert resultados[0].conteudo == trecho


def test_ingestao_e_retomavel(mini_db_com_embeddings: str):
    antes = estatisticas_chunks(mini_db_com_embeddings)
    resumo = rodar_ingestao(provedor_nome="mock", dsn=mini_db_com_embeddings, limite=LIMITE_INGEST)
    depois = estatisticas_chunks(mini_db_com_embeddings)
    assert resumo["chunks"] == 0
    assert depois["chunks"] == antes["chunks"]
    assert antes["chunks"] > 0


def test_filtro_por_condicao(mini_db_com_embeddings: str):
    with conectar(mini_db_com_embeddings) as con:
        condicao_alvo = con.execute(
            """
            SELECT e.cmetadata->>'condicao' AS condicao
            FROM langchain_pg_embedding e
            JOIN langchain_pg_collection c ON c.uuid = e.collection_id
            LIMIT 1
            """
        ).fetchone()["condicao"]
    assert condicao_alvo

    resultados = BuscaRepositorio(mini_db_com_embeddings).buscar_vetorial(
        "qualquer consulta",
        obter_provedor("mock"),
        k=10,
        condicao=condicao_alvo,
    )
    assert resultados
    assert all(r.condicao == condicao_alvo for r in resultados)


def test_busca_sem_chunks_retorna_vazio(mini_db: str, criar_banco_isolado):
    db_vazio = criar_banco_isolado()
    rodar_etl(
        caminho_parquet=PARQUET,
        dsn=db_vazio,
        n_pacientes=10,
        limite_linhas=100,
    )
    resultados = BuscaRepositorio(db_vazio).buscar_vetorial(
        "teste", obter_provedor("mock"), k=3
    )
    assert resultados == []