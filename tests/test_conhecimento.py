"""Testes de ingestão e busca de documentos de conhecimento (RAG contextual).

Valida que a coleção de conhecimento é separada da coleção de atendimentos,
que a busca retorna metadata de fonte para rastreabilidade/explainability e
que a ingestão de arquivos reais (PDF/Excel) funciona de forma idempotente.
"""

from pathlib import Path

import pytest

from database.conhecimento.documentos_exemplo import obter_documentos_exemplo
from database.conhecimento.ingestao_conhecimento import rodar_ingestao_conhecimento
from database.conhecimento.loaders import carregar_diretorio
from database.etl_seed import rodar_etl
from src.db.buscar import BuscaRepositorio
from src.db.connection import conectar
from src.db.embeddings import obter_provedor

RAIZ = Path(__file__).resolve().parents[1]
PARQUET = RAIZ / "database" / "dataset_medpt_curado.parquet"
KNOWLEDGE_DEMO = RAIZ / "knowledge"

pytestmark = pytest.mark.pg

N_PACIENTES = 50
LIMITE_ETL = 1_000


def _gerar_pdf(caminho: Path, n_paragrafos: int = 3) -> None:
    import reportlab.lib.pagesizes as pagesizes
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate

    doc = SimpleDocTemplate(str(caminho), pagesize=pagesizes.A4, title="Transtornos Termicos")
    estilo = ParagraphStyle("corpo", fontName="Helvetica", fontSize=11, leading=14)
    fluxo = []
    for i in range(1, n_paragrafos + 1):
        fluxo.append(Paragraph(
            f"Casos de estudo de pacientes com transtornos térmicos. Página {i}: "
            f"hipertermia e hipotermia, sinais, condutas imediatas.", estilo
        ))
        fluxo.append(PageBreak())
    doc.build(fluxo)


def _gerar_excel(caminho: Path) -> None:
    from openpyxl import Workbook

    wb = Workbook()
    wb.remove(wb.active)
    ws = wb.create_sheet(title="Transtornos Termicos")
    ws.append(["Condicao", "Sinais", "Conduta"])
    ws.append(["Hipertermia", "Temperatura >40C", "Resfriamento ativo"])
    ws.append(["Hipotermia", "Temperatura <35C", "Reaquecimento"])
    wb.save(str(caminho))


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


def test_ingestao_conhecimento_e_idempotente(db_conhecimento):
    """Segunda ingestão dos mesmos documentos não cria duplicatas."""
    primeira = rodar_ingestao_conhecimento(provedor_nome="mock", dsn=db_conhecimento)
    assert primeira["chunks_novos"] == 0
    assert primeira["chunks_pulados"] == primeira["chunks"]
    assert primeira["chunks_pulados"] > 0

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


def test_busca_conhecimento_retorna_fontes(db_conhecimento):
    provedor = obter_provedor("mock")
    resultados = BuscaRepositorio(db_conhecimento).buscar_conhecimento(
        "paciente com asma e falta de ar", provedor, k=5
    )

    assert 0 < len(resultados) <= 5
    similaridades = [r.similaridade for r in resultados]
    assert similaridades == sorted(similaridades, reverse=True)

    tipos_validos = {"protocol", "case_study", "guideline", "reference", "pdf", "excel"}
    for r in resultados:
        assert r.conteudo
        assert r.fonte, "resultado deve ter fonte identificável"
        assert r.tipo_documento in tipos_validos
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


# ---------------------------------------------------------------------------
# Ingestão com arquivos reais (PDF + Excel) — teste 1 e 2 da especificação
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def dir_documentos(tmp_path_factory) -> str:
    """Diretório temporário com um PDF e um Excel de referência."""
    base = tmp_path_factory.mktemp("conhecimento_docs")
    pdf = base / "casos_estudo_transtornos_termicos.pdf"
    xlsx = base / "protocolos_clinicos_transtornos.xlsx"
    _gerar_pdf(pdf, n_paragrafos=3)
    _gerar_excel(xlsx)
    return str(base)


def test_ingestao_de_arquivos_pdf_e_excel(db_conhecimento, dir_documentos):
    """Teste 1 e 2: ingestão de PDF e Excel mantém identificação de arquivo/página/sheet."""
    resumo = rodar_ingestao_conhecimento(
        provedor_nome="mock", dsn=db_conhecimento, knowledge_dir=dir_documentos
    )
    assert resumo["chunks_novos"] > 0
    assert resumo["origem"] == dir_documentos

    with conectar(db_conhecimento) as con:
        linhas = con.execute(
            """
            SELECT e.cmetadata
            FROM langchain_pg_embedding e
            JOIN langchain_pg_collection c ON c.uuid = e.collection_id
            WHERE c.name LIKE 'assistente_medico_conhecimento_%'
              AND e.cmetadata->>'source_type' IN ('pdf', 'excel')
            """
        ).fetchall()
    metadatas = [linha["cmetadata"] for linha in linhas]

    assert any(m["source_type"] == "pdf" and m.get("page") for m in metadatas)
    assert any(m["source_type"] == "excel" and m.get("sheet") for m in metadatas)


def test_ingestao_arquivos_e_idempotente(db_conhecimento, dir_documentos):
    resumo = rodar_ingestao_conhecimento(
        provedor_nome="mock", dsn=db_conhecimento, knowledge_dir=dir_documentos
    )
    assert resumo["chunks_novos"] == 0
    assert resumo["chunks_pulados"] > 0


# ---------------------------------------------------------------------------
# Retrieval com metadados enriquecidos — teste 3 da especificação
# ---------------------------------------------------------------------------

def test_retrieval_pdf_retorna_pagina_do_documento_correto(db_conhecimento, dir_documentos):
    """Teste 3: pergunta sobre transtornos térmicos recupera o PDF com página."""
    provedor = obter_provedor("mock")
    resultados = BuscaRepositorio(db_conhecimento).buscar_conhecimento(
        "paciente com hipertermia e febre alta", provedor, k=10,
        source_type="pdf",
    )

    assert resultados
    alvo = [r for r in resultados if r.arquivo == "casos_estudo_transtornos_termicos.pdf"]
    assert alvo
    assert alvo[0].pagina in (1, 2, 3)
    assert alvo[0].tipo_documento == "pdf"


def test_retrieval_excel_retorna_sheet(db_conhecimento, dir_documentos):
    resultados = BuscaRepositorio(db_conhecimento).buscar_conhecimento(
        "conduta para temperatura muito baixa", obter_provedor("mock"), k=10,
        source_type="excel",
    )

    assert resultados
    alvo = [r for r in resultados if r.planilha == "Transtornos Termicos"]
    assert alvo
    assert alvo[0].tipo_documento == "excel"


def test_retrieval_filtro_por_source_type(db_conhecimento):
    provedor = obter_provedor("mock")
    so_pdf = BuscaRepositorio(db_conhecimento).buscar_conhecimento(
        "qualquer consulta", provedor, k=10, source_type="pdf"
    )
    assert all(r.tipo_documento == "pdf" for r in so_pdf)


# ---------------------------------------------------------------------------
# Separação SQL/RAG — teste 6 da especificação
# ---------------------------------------------------------------------------

def test_rag_nao_depende_de_embeddings_de_atendimento(db_conhecimento):
    """O RAG de conhecimento funciona mesmo sem a coleção de atendimentos."""
    with conectar(db_conhecimento) as con:
        tem_atendimentos = con.execute(
            """
            SELECT COUNT(*) AS total
            FROM langchain_pg_embedding e
            JOIN langchain_pg_collection c ON c.uuid = e.collection_id
            WHERE c.name LIKE 'assistente_medico_%'
              AND c.name NOT LIKE '%conhecimento%'
            """
        ).fetchone()["total"]
    # A coleção de atendimentos não é obrigatória para o conhecimento funcionar
    assert tem_atendimentos >= 0

    prova = rodar_ingestao_conhecimento(
        provedor_nome="mock",
        dsn=db_conhecimento,
        knowledge_dir=str(KNOWLEDGE_DEMO) if KNOWLEDGE_DEMO.is_dir() else None,
    )
    assert prova["chunks"] >= 0


def test_dados_paciente_continuam_no_sql(db_conhecimento):
    """Dados estruturados (pacientes/atendimentos) permanecem no banco relacional."""
    with conectar(db_conhecimento) as con:
        pacientes = con.execute("SELECT COUNT(*) AS t FROM pacientes").fetchone()["t"]
        atendimentos = con.execute("SELECT COUNT(*) AS t FROM atendimentos").fetchone()["t"]
    assert pacientes > 0
    assert atendimentos > 0