# Base de Conhecimento Documental (RAG)

Esta pasta armazena os **documentos de referência** que alimentam a coleção
vetorial de conhecimento contextual.

## Separação conceitual

| Fonte             | Papel                                        | Onde fica                                   |
|-------------------|----------------------------------------------|---------------------------------------------|
| Banco relacional  | Dados estruturados do sistema/paciente        | PostgreSQL (tabelas `pacientes`, `atendimentos`, ...) |
| Base documental   | Conhecimento externo (literatura, protocolos) | `knowledge/` (esta pasta) → vector store    |

**O RAG NÃO deve duplicar os dados do banco relacional.** Ele serve para
recuperar conhecimento documental externo que complementa a análise da LLM,
e deve ser sempre rastreável até o arquivo original.

## Estrutura

```
knowledge/
├── pdf/                        # PDFs reais (PCDTs/manuais MS) + didáticos sintéticos
├── excel/                      # Planilhas de referência/posologia (xlsx)
├── metadados_fontes.json       # Catálogo de fontes (versionado) — ver abaixo
├── RELATORIO_CORPUS.md         # Relatório do corpus (versionado)
└── README.md
```

> `pdf/` e `excel/` **não são versionados** no git (arquivos binários grandes);
> basta rodar os scripts de download/geração para recriá-los.

## Corpus: estrutura e reprodutibilidade

O corpus é **"real ou mock de um real"**: a maior parte vem de publicações reais
do Ministério da Saúde/Conitec (PCDTs e manuais), complementada por conteúdo
didático sintético claramente marcado (`sintetico: true`).

| Script | Função |
|---|---|
| `baixar_fontes_reais.py` | Baixa os PCDTs/manuais reais (17 fontes), valida `%PDF`, grava o catálogo |
| `gerar_dataset_conhecimento.py` | Gera os arquivos didáticos sintéticos (12 especialidades × 3 PDFs + 1 Excel) |
| `gerar_relatorio_corpus.py` | Regenera `RELATORIO_CORPUS.md` a partir do vector store |

Fluxo completo:

```bash
# 1. Baixar as fontes reais (aplica fallbacks e grava knowledge/metadados_fontes.json)
python database/conhecimento/baixar_fontes_reais.py

# 2. Gerar o corpus sintético (fundido no mesmo catálogo com sintetico=true)
python database/conhecimento/gerar_dataset_conhecimento.py

# 3. Ingerir tudo no vector store (idempotente)
python database/conhecimento/ingestao_conhecimento.py --provider mock --knowledge-dir knowledge --reset-colecao

# 4. Regenerar o relatório do corpus
python database/conhecimento/gerar_relatorio_corpus.py --provider mock
```

## Metadados de origem

Cada chunk armazenado carrega, no mínimo:

- `source`: nome do arquivo (ex.: `pcdt_hipertensao_2025.pdf`)
- `source_type`: `pdf` ou `excel`
- `document_title`: título real da fonte + ` - p.{página}` (PDF)
- `file_path`: caminho absoluto
- `page`: número da página (PDF)
- `sheet`: nome da planilha (Excel)

Para fontes catalogadas em `knowledge/metadados_fontes.json`, o loader enriquece
ainda com: `author`, `institution`, `year`, `license`, `url`, `document_type`
(`pcdt`, `manual`, etc.) e `sintetico` (bool). Isso permite exibir **"Fontes
consultadas"** com a publicação real por trás de cada trecho.

### Catálogo de fontes (`metadados_fontes.json`)

Formato:

```jsonc
{
  "versao": 1,
  "gerado_em": "2026-09-05T23:21:31+00:00",
  "fontes": {
    "pcdt_hipertensao_2025.pdf": {
      "title": "Protocolo Clínico e Diretrizes Terapêuticas da Hipertensão Arterial Sistêmica",
      "author": "Ministério da Saúde / Conitec",
      "institution": "Ministério da Saúde (Conitec)",
      "year": "2025",
      "document_type": "pcdt",
      "license": "É permitida a reprodução ... (Ministério da Saúde)",
      "url": "https://www.gov.br/conitec/.../@@display-file/file",
      "sintetico": false,
      "baixado": true
    }
  }
}
```

> O catálogo é **versionado no git** (é pequeno e dá rastreabilidade total);
> os binários (`pdf/`, `excel/`) não.

## Ingestão

```bash
# Ingerir apenas os documentos de exemplo embutidos (compatibilidade)
python database/conhecimento/ingestao_conhecimento.py --provider mock

# Regenerar os documentos de exemplo embutidos (compatibilidade)
python database/conhecimento/gerar_documentos_exemplo.py

# Ingerir o corpus desta pasta (knowledge/)
python database/conhecimento/ingestao_conhecimento.py --provider mock --knowledge-dir knowledge

# Recomeçar do zero (apagar coleção antes)
python database/conhecimento/ingestao_conhecimento.py --provider mock --knowledge-dir knowledge --reset-colecao

# Produção com embeddings OpenAI (text-embedding-3-small)
python database/conhecimento/ingestao_conhecimento.py --provider openai --knowledge-dir knowledge --reset-colecao
```

A ingestão é **idempotente**: cada chunk recebe um `chunk_id` estável derivado
do arquivo + página/sheet + hash do conteúdo. Reprocessar o mesmo arquivo não
gera duplicatas.

## Formato suportado / carga manual

Novos documentos podem ser adicionados **sem alterar código**: basta colocar o
arquivo em `knowledge/pdf/` ou `knowledge/excel/` e rodar a ingestão. Para
mantê-los rastreáveis, adicione uma entrada correspondente em
`metadados_fontes.json` (ou rode pelo script de geração).

| Formato      | Extensões        | Document Loader do LangChain       |
|--------------|------------------|------------------------------------|
| PDF          | `.pdf`           | `PyPDFLoader`                      |
| Excel        | `.xlsx`, `.xls`  | `UnstructuredExcelLoader`          |

> Os documentos sintéticos são **dados de demonstração** (`sintetico: true`) —
> conteúdo plausível, porém não oficial, e **não devem ser usados como base
> para decisões clínicas**.
