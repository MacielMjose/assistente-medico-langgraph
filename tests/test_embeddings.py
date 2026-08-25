import sqlite3
from pathlib import Path

import pytest

from database.embeddings_ingest import rodar_ingestao
from database.etl_seed import rodar_etl
from src.db.embeddings import (
    EmbeddingsMock,
    dividir_em_chunks,
    obter_provedor,
)
from src.db.vector_search import buscar_vetorial, estatisticas_chunks

RAIZ = Path(__file__).resolve().parents[1]
PARQUET = RAIZ / "database" / "dataset_medpt_curado.parquet"

N_PACIENTES = 50
LIMITE_ETL = 1_000
LIMITE_INGEST = 1_000


@pytest.fixture(scope="module")
def mini_db(tmp_path_factory) -> Path:
    caminho = tmp_path_factory.mktemp("embed") / "mini.db"
    rodar_etl(
        caminho_parquet=PARQUET,
        caminho_db=caminho,
        n_pacientes=N_PACIENTES,
        limite_linhas=LIMITE_ETL,
    )
    return caminho


def test_dividir_em_chunks_texto_curto():
    texto = "Paciente relata dor lombar há duas semanas."
    assert dividir_em_chunks(texto, max_chars=600) == [texto]


def test_dividir_em_chunks_nao_corta_palavra():
    texto = ("palavra " * 500).strip()
    chunks = dividir_em_chunks(texto, max_chars=600)
    assert all(len(c) <= 600 for c in chunks)
    assert " ".join(chunks) == texto
    assert all(not c.startswith(" ") for c in chunks)


def test_dividir_em_chunks_normaliza_espacos():
    texto = "linha um\n\nlinha   dois\t\ttres"
    chunks = dividir_em_chunks(texto, max_chars=10)
    assert " ".join(chunks) == "linha um linha dois tres"


def test_provedor_desconhecido():
    with pytest.raises(ValueError):
        obter_provedor("nao-existe")


def test_mock_deterministico():
    p = EmbeddingsMock()
    v1, v2 = p.embed_passagens(["mesmo texto", "mesmo texto"])
    assert v1 == v2
    assert abs(sum(x * x for x in v1) - 1.0) < 1e-6
    assert p.embed_consulta("consulta") != []


@pytest.fixture(scope="module")
def mini_db_com_embeddings(mini_db: Path) -> Path:
    resumo = rodar_ingestao(provedor_nome="mock", caminho_db=mini_db, limite=LIMITE_INGEST)
    assert resumo["atendimentos"] == LIMITE_INGEST
    assert resumo["chunks"] >= LIMITE_INGEST
    return mini_db


def test_busca_vetorial_retorna_top_k_ordenado(mini_db_com_embeddings: Path):
    provedor = EmbeddingsMock()
    resultados = buscar_vetorial("dor de cabeça", provedor, caminho_db=mini_db_com_embeddings, k=5)
    assert 0 < len(resultados) <= 5
    similaridades = [r.similaridade for r in resultados]
    assert similaridades == sorted(similaridades, reverse=True)
    for r in resultados:
        assert r.atendimento_id > 0
        assert r.condicao
        assert r.especialidade_principal
        assert r.conteudo


def test_busca_vetorial_consulta_exata_tem_similaridade_maxima(mini_db_com_embeddings: Path):
    con = sqlite3.connect(mini_db_com_embeddings)
    trecho = con.execute(
        """
        SELECT c.conteudo FROM prontuario_chunks c
        JOIN atendimentos a ON a.id = c.atendimento_id
        WHERE length(c.conteudo) > 30 LIMIT 1
        """
    ).fetchone()[0]
    con.close()

    provedor = EmbeddingsMock()
    resultados = buscar_vetorial(trecho, provedor, caminho_db=mini_db_com_embeddings, k=3)
    assert resultados[0].similaridade > 0.9999
    assert resultados[0].conteudo == trecho


def test_ingestao_e_retomavel(mini_db_com_embeddings: Path):
    antes = estatisticas_chunks(mini_db_com_embeddings)
    resumo = rodar_ingestao(provedor_nome="mock", caminho_db=mini_db_com_embeddings, limite=LIMITE_INGEST)
    depois = estatisticas_chunks(mini_db_com_embeddings)
    assert resumo["chunks"] == 0
    assert depois["chunks"] == antes["chunks"]
    assert antes["por_modelo"] == {"mock-hash": antes["chunks"]}


def test_filtro_por_condicao(mini_db_com_embeddings: Path):
    con = sqlite3.connect(mini_db_com_embeddings)
    condicao_alvo = con.execute(
        "SELECT cond.nome FROM prontuario_chunks c "
        "JOIN atendimentos a ON a.id = c.atendimento_id "
        "JOIN condicoes cond ON cond.id = a.condicao_id LIMIT 1"
    ).fetchone()[0]
    con.close()

    resultados = buscar_vetorial(
        "qualquer consulta",
        EmbeddingsMock(),
        caminho_db=mini_db_com_embeddings,
        k=10,
        condicao=condicao_alvo,
    )
    assert resultados
    assert all(r.condicao == condicao_alvo for r in resultados)


def test_busca_sem_chunks_retorna_vazio(tmp_path):
    from database.etl_seed import rodar_etl as _etl

    db_vazio = tmp_path / "vazio.db"
    rodar_etl(
        caminho_parquet=PARQUET,
        caminho_db=db_vazio,
        n_pacientes=10,
        limite_linhas=100,
    )
    resultados = buscar_vetorial("teste", EmbeddingsMock(), caminho_db=db_vazio, k=3)
    assert resultados == []
