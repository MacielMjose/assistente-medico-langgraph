# Estrutura do Projeto - Refatoração

## Resumo das Mudanças

O projeto foi refatorado para seguir a arquitetura proposta, organizando o código em módulos bem definidos conforme sua responsabilidade.

## Nova Estrutura

```
src/
└── assistente_medico/
    ├── __init__.py                 # Exports principais
    ├── graph/                      # Definições do LangGraph
    │   ├── __init__.py
    │   ├── state.py                # TypedDict DadosPaciente (antes: src/models/dados_paciente.py)
    │   ├── nodes.py                # Funções de nó (antes em main.py)
    │   ├── edges.py                # Lógica de roteamento condicional (antes em main.py)
    │   └── builder.py              # Função build_graph() que compila o StateGraph (antes em main.py)
    │
    ├── llm/                        # Camada de configuração do LLM
    │   ├── __init__.py
    │   └── config.py               # get_llm(), get_api_key() (antes: src/services/llm_provider_service.py)
    │
    ├── chains/                     # Cadeias LangChain (placeholder para futuro)
    │   └── __init__.py
    │
    ├── data/                       # Ingestão e preparo dos dados médicos (placeholder para futuro)
    │   └── __init__.py
    │
    ├── guardrails/                 # Limites de atuação do assistente (placeholder para futuro)
    │   └── __init__.py
    │
    ├── observability/              # Logging e auditoria (placeholder para futuro)
    │   └── __init__.py
    │
    └── api/                        # Camada de exposição FastAPI (placeholder para futuro)
        └── __init__.py

main.py                            # Entry point simplificado
```

## Migração de Arquivos

| Arquivo Anterior | Novo Local | Mudanças |
|---|---|---|
| `src/models/dados_paciente.py` | `src/assistente_medico/graph/state.py` | Mantém conteúdo igual |
| `src/services/llm_provider_service.py` | `src/assistente_medico/llm/config.py` | Mantém conteúdo igual |
| `main.py` (funções) | `src/assistente_medico/graph/nodes.py` | Extraído - funções dos nós |
| `main.py` (funções de roteamento) | `src/assistente_medico/graph/edges.py` | Extraído - lógica condicional |
| `main.py` (StateGraph) | `src/assistente_medico/graph/builder.py` | Extraído em `build_graph()` |
| `main.py` | `main.py` | Simplificado - agora apenas importa e executa |

## Como Usar

O arquivo `main.py` foi simplificado e agora funciona como entry point:

```python
from src.assistente_medico.graph import build_graph

app = build_graph()
resultado = app.invoke({"nome": "José"})
```

## Próximas Estruturas Disponíveis (placeholder)

As seguintes estruturas foram criadas e ficam prontas para implementação futura:

- `src/assistente_medico/chains/` - Para RAG e cadeias de prompt
- `src/assistente_medico/data/` - Para loaders, anonimização e vectorstore
- `src/assistente_medico/guardrails/` - Para validadores e políticas
- `src/assistente_medico/observability/` - Para logging, audit e explainability
- `src/assistente_medico/api/` - Para exposição via FastAPI

## Benefícios da Refatoração

✅ **Separação de responsabilidades** - Cada módulo tem um propósito claro  
✅ **Facilita testes** - Componentes isolados são mais testáveis  
✅ **Escalabilidade** - Estrutura pronta para crescimento  
✅ **Manutenibilidade** - Código mais organizado e fácil de localizar  
✅ **Reusabilidade** - Componentes podem ser importados e reutilizados facilmente
