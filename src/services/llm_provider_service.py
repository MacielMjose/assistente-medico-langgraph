"""Provedor de LLM - Ollama com modelos locais."""

import os
from langchain_ollama import ChatOllama
from dotenv import load_dotenv

OLLAMA_URL_PADRAO = "http://localhost:11434"


class _OllamaCompatWrapper:
    """Wrapper que remove parâmetros não suportados pelo Ollama."""
    def __init__(self, llm: ChatOllama):
        self.llm = llm

    def invoke(self, input: str, **kwargs):
        """Remove max_tokens que Ollama não suporta."""
        # Remove parâmetros não suportados
        kwargs.pop("max_tokens", None)
        kwargs.pop("num_predict", None)
        kwargs.pop("top_p", None)
        return self.llm.invoke(input, **kwargs)

    def __getattr__(self, name):
        """Delega outros atributos ao LLM interno."""
        return getattr(self.llm, name)


def get_llm(**kwargs) -> ChatOllama:
    """Instancia o cliente ChatOllama para modelos locais.

    Configuração via variáveis de ambiente:
    - MEDPT_OLLAMA_CHAT_MODEL: Nome do modelo no Ollama (obrigatório)
      Ex: "qwen-medpt" (seu modelo fine-tuned)
    - MEDPT_OLLAMA_BASE_URL: URL do servidor Ollama (padrão: http://localhost:11434)

    Para usar seu modelo fine-tuned Qwen:
    1. Certifique-se de que o Ollama está rodando: ollama serve
    2. Importe o modelo: ollama create qwen-medpt -f Modelfile
    3. Configure: MEDPT_OLLAMA_CHAT_MODEL=qwen-medpt
    """
    load_dotenv()

    model = os.getenv("MEDPT_OLLAMA_CHAT_MODEL", "").strip()
    if not model:
        raise ValueError(
            "MEDPT_OLLAMA_CHAT_MODEL não encontrado no .env.\n"
            "Configure o nome do modelo no Ollama, ex:\n"
            "MEDPT_OLLAMA_CHAT_MODEL=qwen-medpt"
        )

    base_url = os.getenv("MEDPT_OLLAMA_BASE_URL", OLLAMA_URL_PADRAO).strip() or OLLAMA_URL_PADRAO

    # Parâmetros simples que ChatOllama aceita
    prefs = {
        "base_url": base_url,
        "model": model,
    }

    prefs.update(kwargs)
    ollama_llm = ChatOllama(**prefs)

    # Retorna wrapper que remove parâmetros não suportados
    return _OllamaCompatWrapper(ollama_llm)
