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
├── pdf/      # Artigos, protocolos, estudos de caso (PDF)
└── excel/    # Planilhas de referência (xlsx / xls)
```

Novos documentos podem ser adicionados **sem alterar código**: basta colocar o
arquivo na subpasta correspondente e rodar a ingestão. O pipeline varre o
diretório recursivamente.

## Formatos suportados

| Formato      | Extensões        | Document Loader do LangChain       |
|--------------|------------------|------------------------------------|
| PDF          | `.pdf`           | `PyPDFLoader`                      |
| Excel        | `.xlsx`, `.xls`  | `UnstructuredExcelLoader`          |

## Ingestão

```bash
# Ingerir apenas os documentos de exemplo embutidos (compatibilidade)
python database/conhecimento/ingestao_conhecimento.py --provider mock

# Ingerir os arquivos desta pasta (knowledge/pdf, knowledge/excel)
MEDPT_KNOWLEDGE_DIR=knowledge python database/conhecimento/ingestao_conhecimento.py --provider mock

# Ou informar o diretório direto
python database/conhecimento/ingestao_conhecimento.py --provider mock --knowledge-dir knowledge

# Recomeçar do zero (apagar coleção antes)
python database/conhecimento/ingestao_conhecimento.py --provider mock --knowledge-dir knowledge --reset-colecao
```

A ingestão é **idempotente**: cada chunk recebe um `chunk_id` estável derivado
do arquivo + página/sheet + hash do conteúdo. Reprocessar o mesmo arquivo não
gera duplicatas.

## Metadados de origem

Cada chunk armazenado carrega, no mínimo:

- `source`: nome do arquivo (ex.: `protocolo_asma.pdf`)
- `source_type`: `pdf` ou `excel`
- `document_title`: título derivado do arquivo
- `file_path`: caminho absoluto
- `page`: número da página (PDF)
- `sheet`: nome da planilha (Excel)

Para gerar documentos de demonstração:

```bash
python database/conhecimento/gerar_documentos_exemplo.py
```

> Os documentos gerados são **dados de demonstração** — não são publicações
> reais e não devem ser usados como base para decisões clínicas.
