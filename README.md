# Assistente Médico LangGraph

Sistema de apoio à decisão clínica baseado em LangGraph, PostgreSQL + pgvector e RAG (Retrieval-Augmented Generation) com suporte a múltiplos provedores de LLM.

## 🚀 Quick Start

### Pré-requisitos

- Python 3.10+
- Docker e Docker Compose
- Credenciais AWS (se usar Bedrock) ou chave de API (Groq/OpenAI)

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

## 🧠 Configuração de Provedores LLM

O projeto suporta 4 provedores LLM. A seleção é automática, mas pode ser forçada com `MEDPT_LLM_PROVIDER`.

### 1. AWS Bedrock (Recomendado para Produção)

Executa um modelo customizado (fine-tuned) no AWS Bedrock, reduzindo latência e custos.

**Pré-requisitos:**
- Conta AWS com acesso a Bedrock
- Modelo customizado já criado no Bedrock
- Credenciais AWS configuradas localmente

**Configuração:**

```bash
# .env
MEDPT_LLM_PROVIDER=bedrock
MEDPT_BEDROCK_MODEL_ID=arn:aws:bedrock:us-east-1:123456789012:custom-model/medico-v1
AWS_REGION=us-east-1
# AWS_PROFILE=seu-perfil  # Opcional, usa credenciais padrão se não definido
```

**Credenciais AWS (uma das opções abaixo):**

```bash
# Opção 1: Variáveis de ambiente
export AWS_ACCESS_KEY_ID="sua-chave"
export AWS_SECRET_ACCESS_KEY="sua-senha"

# Opção 2: Arquivo de credenciais (~/.aws/credentials)
[seu-perfil]
aws_access_key_id = sua-chave
aws_secret_access_key = sua-senha

# Opção 3: Usar perfil IAM configurado
export AWS_PROFILE=seu-perfil
```

**Criando e testando o modelo no Bedrock:**

```bash
# 1. Prepare seus dados de treinamento (formato compatível com Bedrock)
# 2. Acesse https://console.aws.amazon.com/bedrock/ → Custom Models
# 3. Crie um modelo customizado com fine-tuning
# 4. Copie o ARN do modelo e configure MEDPT_BEDROCK_MODEL_ID
# 5. Execute o assistente
python main.py
```

---

### 2. Ollama (Desenvolvimento Local)

Executa um modelo locally em um container Docker, sem dependências de nuvem.

**Pré-requisitos:**
- Docker Compose rodando (serviço `ollama`)
- Modelo importado no Ollama

**Configuração:**

```bash
# .env
MEDPT_LLM_PROVIDER=ollama
MEDPT_OLLAMA_BASE_URL=http://localhost:11434
MEDPT_OLLAMA_CHAT_MODEL=seu-modelo-medico
```

**Importar um modelo fine-tuned:**

```bash
# 1. Coloque seu Modelfile e arquivos de modelo no diretório correto
# 2. Execute
docker compose exec ollama ollama create seu-modelo-medico -f /caminho/Modelfile

# 3. Verifique
docker compose exec ollama ollama list
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

### 3. Groq (API Cloud - Padrão)

Usando a API da Groq com raciocínio rápido.

```bash
# .env
GROQ_API_KEY=sua-chave-groq
MEDPT_LLM_PROVIDER=groq
# Opcional
MEDPT_LLM_MODEL=qwen2-7b  # Padrão: qwen/qwen3.6-27b
```

**Obter chave:**
- https://console.groq.com/

---

### 4. OpenAI (API Cloud - Fallback)

Usando a API da OpenAI como fallback.

```bash
# .env
OPENAI_API_KEY=sua-chave-openai
MEDPT_LLM_PROVIDER=openai
# Opcional
MEDPT_LLM_MODEL=gpt-4o-mini  # Padrão
```

---

## 🔄 Ordem de Prioridade (Automática)

Se `MEDPT_LLM_PROVIDER` não estiver definido, o sistema tenta na seguinte ordem:

1. **Bedrock** – Se `MEDPT_BEDROCK_MODEL_ID` estiver configurado
2. **Groq** – Se `GROQ_API_KEY` estiver definida
3. **OpenAI** – Se apenas `OPENAI_API_KEY` estiver definida
4. **Ollama** – Se `MEDPT_OLLAMA_CHAT_MODEL` estiver definido

---

## 📚 Embeddings e RAG

O sistema usa embeddings para recuperar conhecimento contextual (RAG).

```bash
# .env
# Opções: "mock" (padrão, sem API), "openai", "ollama"
MEDPT_EMBEDDING_PROVIDER=mock

# Se usar OpenAI
OPENAI_API_KEY=sua-chave

# Se usar Ollama
MEDPT_OLLAMA_EMBEDDING_MODEL=seu-modelo-embeddings
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
# Com Bedrock
export MEDPT_BEDROCK_MODEL_ID="arn:aws:bedrock:..."
python main.py

# Com Ollama local
export MEDPT_LLM_PROVIDER=ollama
python main.py

# Com Groq
export GROQ_API_KEY="sua-chave"
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
- [LangChain AWS](https://python.langchain.com/docs/integrations/providers/aws/)
- [AWS Bedrock](https://aws.amazon.com/bedrock/)
- [Ollama](https://ollama.ai/)

---

## 📧 Contato

Para dúvidas ou problemas, abra uma issue no repositório.

---

**Última atualização:** 2026-09-11
