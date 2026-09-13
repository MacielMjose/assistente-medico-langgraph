# Assistente Médico LangGraph

Sistema de apoio à decisão clínica baseado em LangGraph, PostgreSQL + pgvector e RAG (Retrieval-Augmented Generation) com suporte a múltiplos provedores de LLM.

## 🚀 Quick Start

### Pré-requisitos

- Python 3.10+
- Docker e Docker Compose
- Ollama (local ou Docker)

### Instalação

1. **Clone e configure o ambiente:**

```bash
git clone <repo-url>
cd assistente-medico-langgraph

# Instale as dependências
pip install -r requirements.txt

# Configure as variáveis de ambiente
cp .env.sample .env
```

2. **Suba o PostgreSQL e Ollama (opcional):**

```bash
docker compose up -d
```

3. **Execute as migrações e seed (se necessário):**

```bash
python database/connection.py  # Testa a conexão
python database/etl_seed.py    # Popula dados iniciais
```

---

## 🧠 Configuração de Ollama

O projeto usa **Ollama local** para executar modelos de chat e embeddings sem dependências de nuvem.

**Pré-requisitos:**
- Docker Compose rodando (serviço `ollama`)
- Modelo de chat importado no Ollama (ex: `assistente_medico_small`)
- Modelo de embeddings (ex: `bge-m3`)

**Configuração:**

```bash
# .env
MEDPT_OLLAMA_BASE_URL=http://localhost:11434
MEDPT_OLLAMA_CHAT_MODEL=assistente_medico_small
MEDPT_EMBEDDING_PROVIDER=ollama
MEDPT_OLLAMA_EMBEDDING_MODEL=bge-m3
```

**Importar modelos:**

```bash
# Baixar modelo de embeddings
ollama pull bge-m3

# Importar modelo customizado (se tiver Modelfile e arquivos GGUF)
# 1. Coloque seu Modelfile no diretório correto
# 2. Execute
ollama create assistente_medico_small -f /caminho/Modelfile

# 3. Verifique
ollama list
```

**Exemplo de Modelfile:**

```dockerfile
FROM /caminho/seu-modelo-base.gguf

# Parâmetros opcionais
PARAMETER temperature 0.7
PARAMETER top_p 0.9
PARAMETER top_k 40
```

---

## 🗂️ Estrutura do Projeto

```
.
├── main.py                          # Ponto de entrada (LangGraph workflow)
├── requirements.txt                 # Dependências Python
├── .env.sample                      # Template de variáveis de ambiente
│
├── src/
│   ├── models/                      # Modelos Pydantic (estado, dados)
│   ├── services/
│   │   └── llm_provider_service.py  # Gerenciamento de provedores LLM
│   ├── db/
│   │   ├── connection.py            # Conexão PostgreSQL
│   │   ├── models.py                # Modelos SQLAlchemy
│   │   ├── repos/                   # Repositórios de dados
│   │   ├── buscar/                  # Busca vetorial (RAG)
│   │   └── embeddings.py            # Provedores de embeddings
│   └── routes/                      # Endpoints da API (se aplicável)
│
├── database/
│   ├── etl_seed.py                  # Seed de dados iniciais
│   ├── embeddings_ingest.py         # Ingestão de conhecimento (RAG)
│   └── migrations/                  # Scripts de migração
│
├── tests/                           # Testes automatizados
│
└── knowledge/
    ├── pdf/                         # Documentos (protocolos, diretrizes)
    └── excel/                       # Planilhas de referência
```

---

## 🧪 Executando o Assistente

```bash
# Certifique-se de que Ollama está rodando
ollama serve

# Em outro terminal, execute
python main.py
```

---

## 🛡️ Segurança e Conformidade

O assistente implementa guardrails para:

✅ **Validação de Contexto Médico** – Bloqueia perguntas fora do escopo de saúde  
✅ **Verificação de Alergias** – Detecta conflitos entre medicamentos e alergias  
✅ **Disclaimer Automático** – Sempre inclui aviso: análise é apoio, não prescrição  
✅ **Auditoria** – Todos os acessos são registrados em log  

---

## 📝 Testes

```bash
# Rodas testes unitários
pytest tests/ -v

# Com testes de integração (PostgreSQL)
export MEDPT_TESTAR_PG=1
pytest tests/ -v
```

---

## 🔗 Documentação

- [LangGraph](https://langchain-ai.github.io/langgraph/)
- [Ollama](https://ollama.ai/)
- [LangChain Ollama](https://python.langchain.com/docs/integrations/llms/ollama/)

---

## 📧 Contato

Para dúvidas ou problemas, abra uma issue no repositório.

---

**Última atualização:** 2026-09-13
