"""Testes dos Document Loaders do LangChain para a base de conhecimento.

Valida que PDFs e planilhas são carregados pelos loaders oficiais do LangChain
(PyPDFLoader / UnstructuredExcelLoader) preservando a rastreabilidade de origem
(source, source_type, page, sheet, document_title, file_path).

Os testes geram arquivos temporários reais (PDF e Excel) para exercitar o
fluxo completo de carregamento, sem depender do PostgreSQL.
"""

from pathlib import Path

import pytest

from database.conhecimento.loaders import (
    carregar_diretorio,
    carregar_documento,
    carregar_excel,
    carregar_pdf,
    documento_resumo,
    gerar_chunk_id,
)


def _gerar_pdf(caminho: Path, n_paragrafos: int = 3) -> None:
    import reportlab.lib.pagesizes as pagesizes
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate

    doc = SimpleDocTemplate(
        str(caminho),
        pagesize=pagesizes.A4,
        title="Documento de Teste",
    )
    estilo = ParagraphStyle("corpo", fontName="Helvetica", fontSize=11, leading=14)
    historia = [
        Paragraph(f"Parágrafo de teste número {i}: hipertensão e cuidados.", estilo)
        for i in range(1, n_paragrafos + 1)
    ]
    # uma página por parágrafo
    fluxo = []
    for p in historia:
        fluxo.append(p)
        fluxo.append(PageBreak())
    doc.build(fluxo)


def _gerar_excel(caminho: Path) -> None:
    from openpyxl import Workbook

    wb = Workbook()
    wb.remove(wb.active)
    ws = wb.create_sheet(title="Plano de Tratamento")
    ws.append(["Farmaco", "Indicacao", "Observacao"])
    ws.append(["Losartana", "Hipertensao", "50-100mg/dia"])
    ws.append(["Metformina", "Diabetes tipo 2", "850mg 2x/dia"])
    wb.save(str(caminho))


@pytest.fixture
def pdf_teste(tmp_path: Path) -> Path:
    return tmp_path / "documento_teste.pdf"


@pytest.fixture
def excel_teste(tmp_path: Path) -> Path:
    return tmp_path / "planilha_teste.xlsx"


def test_carregar_pdf_usa_pypdf_loader_e_preserva_origem(pdf_teste):
    _gerar_pdf(pdf_teste, n_paragrafos=3)
    docs = carregar_pdf(pdf_teste)

    assert len(docs) >= 1
    for doc in docs:
        meta = doc.metadata
        assert meta["source"] == "documento_teste.pdf"
        assert meta["source_type"] == "pdf"
        assert meta["document_title"].startswith("Documento Teste - p.")
        assert meta["file_path"].endswith("documento_teste.pdf")
        assert doc.page_content.strip()


def test_carregar_pdf_paginas_1based_e_ordenadas(pdf_teste):
    _gerar_pdf(pdf_teste, n_paragrafos=3)
    docs = carregar_pdf(pdf_teste)

    paginas = [d.metadata["page"] for d in docs]
    assert paginas == sorted(paginas)
    assert paginas == list(range(1, len(paginas) + 1))


def test_carregar_excel_usa_unstructured_e_preserva_sheet(excel_teste):
    _gerar_excel(excel_teste)
    docs = carregar_excel(excel_teste)

    assert len(docs) == 1
    doc = docs[0]
    meta = doc.metadata
    assert meta["source"] == "planilha_teste.xlsx"
    assert meta["source_type"] == "excel"
    assert meta["sheet"] == "Plano de Tratamento"
    assert meta["file_path"].endswith("planilha_teste.xlsx")
    assert "Losartana" in doc.page_content
    assert "Metformina" in doc.page_content


def test_carregar_documento_detecta_formato_pelo_sufixo(pdf_teste, excel_teste):
    _gerar_pdf(pdf_teste, n_paragrafos=1)
    _gerar_excel(excel_teste)

    pdf_docs = carregar_documento(pdf_teste)
    excel_docs = carregar_documento(excel_teste)

    assert all(d.metadata["source_type"] == "pdf" for d in pdf_docs)
    assert all(d.metadata["source_type"] == "excel" for d in excel_docs)


def test_carregar_documento_formato_nao_suportado(tmp_path):
    arquivo = tmp_path / "texto.txt"
    arquivo.write_text("conteúdo")

    with pytest.raises(ValueError, match="Formato não suportado"):
        carregar_documento(arquivo)


def test_carregar_diretorio_varre_recursivamente(tmp_path):
    sub = tmp_path / "subdir"
    sub.mkdir()
    pdf = tmp_path / "a.pdf"
    xls = sub / "b.xlsx"
    _gerar_pdf(pdf, n_paragrafos=1)
    _gerar_excel(xls)

    docs = carregar_diretorio(tmp_path)

    assert len(docs) == 2  # 1 página do PDF + 1 tabela do Excel
    tipos = sorted({d.metadata["source_type"] for d in docs})
    assert tipos == ["excel", "pdf"]


def test_gerar_chunk_id_estavel_e_deterministico(pdf_teste):
    _gerar_pdf(pdf_teste, n_paragrafos=2)
    docs = carregar_pdf(pdf_teste)

    id_1 = gerar_chunk_id(docs[0], 0)
    id_1_repetido = gerar_chunk_id(docs[0], 0)
    assert id_1 == id_1_repetido
    assert "documento_teste.pdf" in id_1
    assert "::" in id_1

    id_2 = gerar_chunk_id(docs[1], 0)
    assert id_1 != id_2  # página diferente -> chunk_id diferente


def test_documento_resumo_legivel(pdf_teste):
    _gerar_pdf(pdf_teste, n_paragrafos=1)
    docs = carregar_pdf(pdf_teste)

    resumo = documento_resumo(docs[0])
    assert "pdf" in resumo["origem"]
    assert "documento_teste.pdf" in resumo["origem"]
    assert resumo["len_conteudo"] > 0