"""Gera o relatório do corpus documental de conhecimento (RELATORIO_CORPUS.md).

Consulta a coleção ``*_conhecimento_*`` do PGVector e produz um resumo de
rastreabilidade do corpus: total de fontes/chunks, distribuição por origem
(instituição/ano/tipo), e a tabela fonte a fonte. O relatório é estável e
regenerável a qualquer momento (não depende do provedor de embeddings).

Uso:
    python database/conhecimento/gerar_relatorio_corpus.py            # provider mock
    python database/conhecimento/gerar_relatorio_corpus.py --provider openai

Gera:
    knowledge/RELATORIO_CORPUS.md
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Iterable

RAIZ_PROJETO = Path(__file__).resolve().parents[2]
if str(RAIZ_PROJETO) not in sys.path:
    sys.path.insert(0, str(RAIZ_PROJETO))

from src.db.connection import conectar, resolver_dsn

DESTINO = RAIZ_PROJETO / "knowledge" / "RELATORIO_CORPUS.md"
ALVO_MIN, ALVO_MAX = 5_000, 15_000

ORDEM_TIPOS = [
    "pcdt", "livro_pcdt", "relatorio_pcdt", "manual", "manual_didatico",
    "guia_prescricao", "protocolo_didatico", "tabela_posologia",
]


def _consultar(dsn: str) -> list[dict]:
    """Retorna uma linha por chunk de qualquer coleção *_conhecimento_*."""
    with conectar(dsn) as con:
        linhas = con.execute(
            """
            SELECT c.name AS colecao,
                   e.cmetadata->>'source'       AS source,
                   e.cmetadata->>'document_title' AS titulo,
                   e.cmetadata->>'institution'  AS instituicao,
                   e.cmetadata->>'year'         AS ano,
                   e.cmetadata->>'document_type' AS tipo,
                   COALESCE((e.cmetadata->>'sintetico')::boolean, false) AS sintetico
            FROM langchain_pg_embedding e
            JOIN langchain_pg_collection c ON c.uuid = e.collection_id
            WHERE c.name LIKE '%conhecimento%'
            ORDER BY source, 5, c.name
            """
        ).fetchall()
    return [dict(linha) for linha in linhas]


def _formata(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def _tabela_md(linhas: Iterable[dict]) -> str:
    linhas = list(linhas)
    if not linhas:
        return "_sem registros_"
    cab = "| Fonte | Título | Instituição | Ano | Tipo | Sintético | Chunks |"
    sep = "|---|---|---|---|---|---|---:|"
    corpo = []
    for r in sorted(linhas, key=lambda r: (-r["n"], r["source"] or "")):
        sint = "sim" if r["sintetico"] else "—"
        corpo.append(
            f"| `{r['source'] or '?'}` | {r['titulo'] or '—'} | "
            f"{r['instituicao'] or '—'} | {r['ano'] or '—'} | "
            f"{r['tipo'] or '—'} | {sint} | {_formata(r['n'])} |"
        )
    return "\n".join([cab, sep, *corpo])


def main() -> None:
    parser = argparse.ArgumentParser(description="Gera RELATORIO_CORPUS.md.")
    parser.add_argument("--provider", default="mock", choices=["mock", "openai"])
    parser.add_argument("--destino", type=str, default=None)
    args = parser.parse_args()

    dsn = resolver_dsn(None)
    linhas = _consultar(dsn)
    if not linhas:
        print("[relatório] nenhum chunk de conhecimento no banco. "
              "Rode a ingestão antes (ingestao_conhecimento.py).")
        raise SystemExit(1)

    # Agregação por ARQUIVO (fonte física): uma linha por PDF/Excel, com a soma
    # dos chunks de todas as páginas/planilhas (o document_title real carrega o
    # sufixo " - p.N", que removemos aqui para exibir apenas o título da fonte).
    por_arquivo: dict[str, dict] = {}
    for r in linhas:
        chave = r["source"] or "?"
        if chave not in por_arquivo:
            titulo = re.sub(r"\s*-\s*p\.\d+$", "", r["titulo"] or "")
            por_arquivo[chave] = {
                **r,
                "titulo_base": titulo,
                "n": 0,
            }
        por_arquivo[chave]["n"] += 1
    fontes = list(por_arquivo.values())

    for r in fontes:
        r["titulo"] = r.pop("titulo_base")

    total_chunks = sum(r["n"] for r in fontes)
    total_pdf = sum(r["n"] for r in fontes if r["source"] and r["source"].endswith(".pdf"))
    total_excel = sum(r["n"] for r in fontes if r["source"] and r["source"].endswith((".xlsx", ".xls")))
    n_fontes = len(fontes)
    sinteticos = [r for r in fontes if r["sintetico"]]
    reais = [r for r in fontes if not r["sintetico"]]

    por_inst = Counter()
    for r in fontes:
        por_inst[r["instituicao"] or "(sem instituição)"] += r["n"]
    por_ano = Counter()
    for r in fontes:
        por_ano[(r["ano"] or "(sem ano)")] += r["n"]
    por_tipo = Counter()
    for r in fontes:
        por_tipo[r["tipo"] or "(sem tipo)"] += r["n"]

    no_alvo = (
        "DENTRO do alvo de 5.000 a 15.000 chunks." if ALVO_MIN <= total_chunks <= ALVO_MAX
        else f"FORA do alvo de {_formata(ALVO_MIN)}–{_formata(ALVO_MAX)} chunks."
    )

    tabela_inst = "\n".join(
        f"| {inst or '—'} | {_formata(n)} |"
        for inst, n in por_inst.most_common()
    )
    ordem_anos = sorted(por_ano, key=lambda a: a if isinstance(a, str) and a.isdigit() else 0, reverse=True)
    tabela_ano = "\n".join(
        f"| {ano or '—'} | {_formata(por_ano[ano])} |"
        for ano in ordem_anos
    )
    tabela_tipo = "\n".join(
        f"| {tipo or '—'} | {_formata(por_tipo[tipo])} |"
        for tipo in sorted(por_tipo, key=lambda t: (-por_tipo[t], ORDEM_TIPOS.index(t) if t in ORDEM_TIPOS else 99))
    )

    gerado_em = dt.datetime.now(dt.timezone.utc).astimezone().strftime("%d/%m/%Y %H:%M")
    relatorio = f"""# Relatório do Corpus de Conhecimento (RAG)

Gerado em: {gerado_em} · Coleção: `{linhas[0]['colecao']}` (e demais `*_conhecimento_*`)

## Resumo

| Métrica | Valor |
|---|---:|
| Fontes documentais catalogadas | {_formata(n_fontes)} |
| Chunks totais no vector store | **{_formata(total_chunks)}** |
| — chunks de PDF | {_formata(total_pdf)} |
| — chunks de planilha (Excel) | {_formata(total_excel)} |
| — chunks de fontes reais (PCDTs/manuais MS) | {_formata(sum(r['n'] for r in reais))} |
| — chunks de fontes sintéticas (mock didático) | {_formata(sum(r['n'] for r in sinteticos))} |

**Alvo da especificação (5.000–15.000 chunks): {no_alvo}**

## Fontes (fonte a fonte)

{_tabela_md(fontes)}

## Distribuição por instituição

| Instituição | Chunks |
|---:|---:|
{tabela_inst}

## Distribuição por ano

| Ano | Chunks |
|---:|---:|
{tabela_ano}

## Distribuição por tipo de documento

| Tipo | Chunks |
|---:|---:|
{tabela_tipo}

## Rastreabilidade e reprodutibilidade

- **Fontes reais**: curadas e baixadas por
  `database/conhecimento/baixar_fontes_reais.py` (validação de `%PDF`, múltiplas
  URLs com fallback). O catálogo com título/autor/instituição/ano/licença/URL de
  cada fonte está em `knowledge/metadados_fontes.json` (versionado).
- **Fontes sintéticas**: geradas por
  `database/conhecimento/gerar_dataset_conhecimento.py` (12 especialidades ×
  manual + guia de prescrição + protocolo de atendimento + tabela de posologia).
  Todo chunk sintético carrega `sintetico: true` e licença didática.
- **Ingestão**: `python database/conhecimento/ingestao_conhecimento.py
  --provider mock --knowledge-dir knowledge --reset-colecao`. O processo é
  idempotente (chunk_id estável = fonte + localização + hash do conteúdo).
- **Relatório**: `python database/conhecimento/gerar_relatorio_corpus.py`.

Para o **provedor OpenAI** (produção), repetir a ingestão com `--provider openai`
(embeddings com 1536 dimensões em uma coleção separada) e regenerar este
relatório com `--provider openai`.

## Consultas de validação sugeridas

Consultas de teste para conferir que o corpus recupera o contexto esperado na
API/UI (o resultado real depende do provedor de embeddings em uso):

| Consulta | Fontes esperadas no contexto |
|---|---|
| "Hipertensão arterial sistêmica medicamentos de primeira linha" | `pcdt_hipertensao_2025.pdf` |
| "Crise asmática salbutamol dose" | `pcdt_asma_2021.pdf` |
| "Conduta na pré-eclâmpsia grave sulfato de magnésio" | `manual_condutas_obstetricia.pdf` (sintético) |
| "Metformina no diabete melito tipo 2" | `pcdt_diabete_melito_tipo2_2026.pdf` |
| "Posologia de medicamentos em pediatria" | `posologia_pediatria.xlsx` (sintético) |
| "Linhas de organização da Rede de Atenção às Urgências" | `manual_instrutivo_rue.pdf`, `politica_nacional_atencao_urgencias_3ed.pdf` |

Toda resposta do agente deve citar a fonte (`source`/`document_title`/`page`);
o corpus foi desenhado para tornar essas citações rastreáveis até o arquivo
original.
"""
    destino = Path(args.destino) if args.destino else DESTINO
    destino.write_text(relatorio, encoding="utf-8")
    print(f"[relatório] {len(fontes)} fontes, {total_chunks} chunks -> {destino}")


if __name__ == "__main__":
    main()