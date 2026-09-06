"""Gera documentos de exemplo (PDF + Excel) para a base de conhecimento.

Este script cria arquivos de demonstração em ``knowledge/pdf`` e
``knowledge/excel`` que podem ser ingeridos pelo pipeline RAG. O objetivo é
validar o fluxo completo: Document Loader -> chunking -> embeddings -> PGVector.

Os conteúdos gerados são DADOS DE DEMONSTRAÇÃO (não são publicações reais) e
não devem ser usados como base para decisões clínicas.

Uso:
    python database/conhecimento/gerar_documentos_exemplo.py
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

KNOWLEDGE = RAIZ / "knowledge"
PDF_DIR = KNOWLEDGE / "pdf"
EXCEL_DIR = KNOWLEDGE / "excel"

# Conteúdo dos "casos de estudo de transtornos térmicos" (referido na
# especificação como exemplo de documento recuperável).
TEXTO_TRANSTORNOS_TERMICOS = [
    """Casos de estudo de pacientes com transtornos térmicos. Hipertermia:
    elevação da temperatura corporal acima de 40°C com falha dos mecanismos de
    termorregulação. Causas: exposição prolongada ao calor, exercício intenso,
    desidratação, uso de medicamentos que reduzem a sudorese. Sinais clínicos:
    pele quente e seca, confusão, convulsões, taquicardia, hipotensão.
    Tratamento imediato: resfriamento ativo, reposição volêmica, monitorização
    de temperatura retal e vigilância de rabdomiólise e lesão renal.""",
    """Casos de estudo de pacientes com transtornos térmicos (continuação).
    Hipotermia: temperatura central abaixo de 35°C. Classificação: leve
    (32-35°C), moderada (28-32°C), grave (abaixo de 28°C). Manifestações:
    tremor, letargia, bradicardia, arritmias, depressão do nível de
    consciência. Manejo: reaquecimento passivo na forma leve, reaquecimento
    ativo externo na moderada, e reaquecimento ativo interno (via aérea
    aquecida, infusão morna, lavagem corporal) na grave. Evitar manuseio
    brusco que precipite fibrilação ventricular.""",
    """Prevenção de transtornos térmicos em pacientes acamados e idosos.
    Estratégias: hidratação adequada (30-40 mL/kg/dia), ambientes ventilados,
    roupas leves, monitorização de exposição ao calor nas ondas de calor.
    Em ambiente hospitalar: controle de temperatura ambiente, avaliação
    periódica de sinais vitais e resposta térmica. Considerar risco elevado
    em uso de diuréticos, anticolinérgicos e em pacientes com diabetes.""",
]

CONTEUDO_PROTOCOLO_XLSX = {
    "Transtornos Termicos": [
        ["Condicao", "Sinais", "Conduta", "Urgencia"],
        ["Hipertermia", "Temperatura >40C, pele quente e seca", "Resfriamento ativo, reposicao volemica", "Alta"],
        ["Hipotermia leve", "Temperatura 32-35C, tremor", "Reaquecimento passivo", "Media"],
        ["Hipotermia moderada", "Temperatura 28-32C, letargia", "Reaquecimento ativo externo", "Alta"],
        ["Hipotermia grave", "Temperatura <28C, arritmias", "Reaquecimento ativo interno", "Critica"],
    ],
    "Protocolo Antiemeticos": [
        ["Farmaco", "Dose", "Via", "Observacao"],
        ["Ondansetrona", "4-8mg", "IV/IM", "Evitar se prolongamento QT"],
        ["Metoclopramida", "10mg ate 3x/dia", "SC/IM/IV", "Risco de distonia, usar breve"],
        ["Dimenidrinato", "50mg a cada 8h", "VO", "Sonolencia, evitar em idosos"],
    ],
}


def gerar_pdf(caminho: Path) -> None:
    import reportlab.lib.pagesizes as pagesizes
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer

    doc = SimpleDocTemplate(
        str(caminho),
        pagesize=pagesizes.A4,
        title="Casos de Estudo - Transtornos Termicos",
        author="Data de Demonstracao",
    )
    estilos = [
        ParagraphStyle(
            "titulo",
            fontName="Helvetica-Bold",
            fontSize=16,
            spaceAfter=12,
        ),
        ParagraphStyle(
            "corpo",
            fontName="Helvetica",
            fontSize=11,
            leading=14,
            spaceAfter=10,
        ),
    ]
    historia = [
        Paragraph("Casos de Estudo - Transtornos Termicos", estilos[0]),
    ]
    for i, paragrafo in enumerate(TEXTO_TRANSTORNOS_TERMICOS, start=1):
        historia.append(Paragraph(paragrafo, estilos[1]))
        if i < len(TEXTO_TRANSTORNOS_TERMICOS):
            historia.append(PageBreak())
    doc.build(historia)


def gerar_excel(caminho: Path) -> None:
    from openpyxl import Workbook

    wb = Workbook()
    wb.remove(wb.active)
    for nome_sheet, linhas in CONTEUDO_PROTOCOLO_XLSX.items():
        ws = wb.create_sheet(title=nome_sheet[:31])
        for linha in linhas:
            ws.append(linha)
    wb.save(str(caminho))


def main() -> None:
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    EXCEL_DIR.mkdir(parents=True, exist_ok=True)

    pdf_alvo = PDF_DIR / "casos_estudo_transtornos_termicos.pdf"
    excel_alvo = EXCEL_DIR / "protocolos_clinicos_transtornos.xlsx"

    gerar_pdf(pdf_alvo)
    gerar_excel(excel_alvo)

    print("Documentos de exemplo gerados:")
    print(f"  {pdf_alvo}")
    print(f"  {excel_alvo}")


if __name__ == "__main__":
    main()
