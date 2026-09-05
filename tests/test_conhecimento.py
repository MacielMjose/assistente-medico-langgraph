"""Testes de ingestão e busca de documentos de conhecimento (RAG contextual).

Valida que a coleção de conhecimento é separada da coleção de atendimentos e
que a busca retorna metadata de fonte para rastreabilidade/explainability.
"""

from pathlib import Path

import pytest

from database.conhecimento.documentos_exemplo import obter_documentos_exemplo
from database.conhecimento.ingestao_conhecimento import rodar_ingestao_conhecimento
from database.etl_seed import rodar_etl
from src.db.buscar import BuscaRepositorio
from src.db.connection import conectar
from src.db.embeddings import obter_provedor

RAIZ = Path(__file__).resolve().parents[1]
PARQUET = RAIZ / "database" / "dataset_medpt_curado.parquet"

pytestmark = pytest.mark.pg

N_PACIENTES = 50
LIMITE_ETL = 1_000


@pytest.fixture(scope="module")
def db_conhecimento(dsn_teste) -> str:
    rodar_etl(
        caminho_parquet=PARQUET,
        dsn=dsn_teste,
        n_pacientes=N_PACIENTES,
        limite_linhas=LIMITE_ETL,
    )
    rodar_ingestao_conhecimento(provedor_nome="mock", dsn=dsn_teste)
    return dsn_teste


def test_documentos_exemplo_sao_validos():
    documentos = obter_documentos_exemplo()
    assert len(documentos) >= 5

    tipos = set()
    for doc in documentos:
        assert doc.page_content.strip()
        meta = doc.metadata
        assert meta.get("source"), "metadata deve conter 'source'"
        assert meta.get("document_type"), "metadata deve conter 'document_type'"
        assert meta.get("title"), "metadata deve conter 'title'"
        tipos.add(meta.get("document_type"))

    assert tipos.issuperset({"protocol", "case_study", "guideline", "reference"})


def test_ingestao_conhecimento_insere_chunks(db_conhecimento):
    with conectar(db_conhecimento) as con:
        total = con.execute(
            """
            SELECT COUNT(*) AS total
            FROM langchain_pg_embedding e
            JOIN langchain_pg_collection c ON c.uuid = e.collection_id
            WHERE c.name LIKE 'assistente_medico_conhecimento_%'
            """
        ).fetchone()["total"]
    assert total > 0


def test_ingestao_conhecimento_e_retomavel(db_conhecimento):
    resumo = rodar_ingestao_conhecimento(provedor_nome="mock", dsn=db_conhecimento)
    assert resumo["chunks"] > 0


def test_busca_conhecimento_retorna_fontes(db_conhecimento):
    provedor = obter_provedor("mock")
    resultados = BuscaRepositorio(db_conhecimento).buscar_conhecimento(
        "paciente com asma e falta de ar", provedor, k=5
    )

    assert 0 < len(resultados) <= 5
    similaridades = [r.similaridade for r in resultados]
    assert similaridades == sorted(similaridades, reverse=True)

    for r in resultados:
        assert r.conteudo
        assert r.fonte, "resultado deve ter fonte identificável"
        assert r.tipo_documento in {"protocol", "case_study", "guideline", "reference"}
        assert r.titulo
        assert r.metadata_completa.get("source")


def test_busca_conhecimento_nao_mistura_com_atendimentos(db_conhecimento):
    provedor = obter_provedor("mock")
    resultados = BuscaRepositorio(db_conhecimento).buscar_conhecimento(
        "dor", provedor, k=3
    )
    assert all(not hasattr(r, "atendimento_id") for r in resultados)


def test_colecao_conhecimento_e_diferente_da_colecao_atendimentos(db_conhecimento):
    with conectar(db_conhecimento) as con:
        nomes = con.execute(
            "SELECT DISTINCT name FROM langchain_pg_collection ORDER BY name"
        ).fetchall()
    nomes_colecoes = {linha["name"] for linha in nomes}
    assert any("_conhecimento_" in nome for nome in nomes_colecoes)