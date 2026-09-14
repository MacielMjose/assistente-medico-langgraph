# Assistente Médico LangGraph

Sistema de apoio à decisão clínica baseado em LangGraph, PostgreSQL + pgvector e RAG (Retrieval-Augmented Generation) usando Ollama para modelos locais.

## 🚀 Quick Start

### Pré-requisitos

- **Python 3.10+**
- **Docker e Docker Compose** (para PostgreSQL e Ollama)
- **Ollama** (local ou Docker) - para executar modelos de LLM e embeddings
- **PostgreSQL 14+** (iniciado via Docker Compose)
- **Git**

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

2. **Suba os serviços (PostgreSQL e Ollama):**

```bash
docker compose up -d
```

Este comando inicia:
- **PostgreSQL 14** com extensão pgvector (para busca vetorial RAG)
- **Ollama** (para executar modelos de LLM e embeddings)

Verifique se os containers estão rodando:
```bash
docker compose ps
```

3. **Baixe e configure os modelos do Ollama:**

```bash
# Modelo de embeddings
ollama pull bge-m3

# Modelo de chat (customizado ou padrão)
# Se tiver seu modelo fine-tuned, crie com:
# ollama create assistente_medico_small -f ./Modelfile
# Caso contrário, use um modelo disponível:
ollama pull qwen2:7b
```

4. **Execute as migrações e seed:**

```bash
python database/connection.py  # Testa a conexão com PostgreSQL
python database/etl_seed.py    # Popula dados iniciais no banco
```

---

## ⚙️ Variáveis de Ambiente

Configure o arquivo `.env` com as seguintes variáveis (copie de `.env.sample`):

```bash
# Ollama
MEDPT_OLLAMA_BASE_URL=http://localhost:11434
MEDPT_OLLAMA_CHAT_MODEL=qwen2:7b  # ou seu modelo fine-tuned
MEDPT_EMBEDDING_PROVIDER=ollama
MEDPT_OLLAMA_EMBEDDING_MODEL=bge-m3

# PostgreSQL
DATABASE_URL=postgresql://user:password@localhost:5432/assistente_medico
MEDPT_DB_HOST=localhost
MEDPT_DB_PORT=5432
MEDPT_DB_USER=postgres
MEDPT_DB_PASSWORD=postgres
MEDPT_DB_NAME=assistente_medico
```

Verifique `.env.sample` para todas as variáveis disponíveis.

---

## 🧠 Configuração de Ollama

O projeto usa **Ollama local** para executar modelos de chat e embeddings sem dependências de nuvem.

Os modelos são baixados e configurados no passo 3 da instalação. Se precisar de um modelo customizado com Modelfile:

```dockerfile
# Exemplo de Modelfile
FROM /caminho/seu-modelo-base.gguf

# Parâmetros opcionais
PARAMETER temperature 0.7
PARAMETER top_p 0.9
PARAMETER top_k 40
```

Para criar o modelo no Ollama:
```bash
ollama create assistente_medico_small -f ./Modelfile
```

Consulte a [documentação do Ollama](https://ollama.ai/) para mais detalhes sobre criar e customizar modelos.

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
│   │   └── llm_provider_service.py  # Cliente Ollama para LLM local
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

## 🚀 Executando o Assistente

Antes de executar, verifique se tudo está pronto:

```bash
# 1. Verifique se os containers estão rodando
docker compose ps

# 2. Verifique se Ollama tem os modelos necessários
ollama list

# 3. Teste a conexão com PostgreSQL
python database/connection.py

# 4. Execute o assistente
python main.py
```

---

## 🔧 Troubleshooting

### "Connection refused" ao conectar no PostgreSQL
```bash
# Verifique se PostgreSQL está rodando
docker compose ps

# Se não estiver, inicie
docker compose up -d

# Verifique as credenciais em .env
```

### "Ollama connection refused"
```bash
# Verifique se Ollama está rodando
docker compose ps

# Ou, se rodando localmente fora do Docker
ollama serve
```

### Modelos não encontrados no Ollama
```bash
# Verifique modelos disponíveis
ollama list

# Puxe os modelos necessários
ollama pull bge-m3
ollama pull qwen2:7b
```

### Erro ao importar módulos Python
```bash
# Reinstale as dependências
pip install --upgrade pip
pip install -r requirements.txt
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

**Última atualização:** 2026-09-14
