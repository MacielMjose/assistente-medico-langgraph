import os
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

GROQ_URL = "https://api.groq.com/openai/v1"
OPENAI_URL = "https://api.openai.com/v1"

MODELO_GROQ = "qwen/qwen3.6-27b"
MODELO_OPENAI = "gpt-4o-mini"


def get_api_key(env_var_name: str = "GROQ_API_KEY") -> str | None:
    """Retorna a chave de API para o provedor LLM.

    Prioriza ``GROQ_API_KEY`` (padrão histórico), mas aceita ``OPENAI_API_KEY``
    como fallback — permitindo rodar a aplicação apenas com uma chave da OpenAI.
    """
    load_dotenv()
    if env_var_name == "GROQ_API_KEY":
        for chave in ("GROQ_API_KEY", "OPENAI_API_KEY"):
            valor = os.getenv(chave, "").strip()
            if valor:
                return valor
        raise ValueError(
            "Nenhuma chave de LLM encontrada. Defina GROQ_API_KEY ou "
            "OPENAI_API_KEY no arquivo .env."
        )
    valor = os.getenv(env_var_name, "").strip()
    if not valor:
        raise ValueError(f"{env_var_name} não encontrado no arquivo .env")
    return valor


def _preferencias_llm() -> dict:
    """Decide o provedor LLM a partir das chaves presentes no ambiente.

    Retorna um dicionário de kwargs para ``ChatOpenAI``: ``api_key``, ``base_url``
    (via ``MEDPT_LLM_BASE_URL`` para qualquer provedor de API compatível com o
    formato da OpenAI) e ``model`` (via ``MEDPT_LLM_MODEL``).
    """
    groq = os.getenv("GROQ_API_KEY", "").strip()
    openai = os.getenv("OPENAI_API_KEY", "").strip()

    if groq:
        return {
            "api_key": groq,
            "base_url": os.getenv("MEDPT_LLM_BASE_URL", GROQ_URL) or GROQ_URL,
            "model": os.getenv("MEDPT_LLM_MODEL", MODELO_GROQ) or MODELO_GROQ,
            "reasoning_effort": os.getenv("MEDPT_LLM_REASONING_EFFORT") or "none",
            "max_tokens":1000
        } 
        
    if openai:
        return {
            "api_key": openai,
            "base_url": os.getenv("MEDPT_LLM_BASE_URL", OPENAI_URL) or OPENAI_URL,
            "model": os.getenv("MEDPT_LLM_MODEL", MODELO_OPENAI) or MODELO_OPENAI,
        }
    return {}


def get_llm(
    url: str | None = None, model: str | None = None, **kwargs
) -> ChatOpenAI:
    """Instancia o ChatOpenAI conforme as chaves disponíveis.

    - Com ``GROQ_API_KEY``: usa a Groq (padrão, com ``reasoning_effort``).
    - Com apenas ``OPENAI_API_KEY``: usa a OpenAI (sem ``reasoning_effort``,
      pois o gpt-4o-mini não suporta esse parâmetro).
    - ``url``/``model`` (ou envs ``MEDPT_LLM_BASE_URL``/``MEDPT_LLM_MODEL``)
      permitem apontar para qualquer provedor de API compatível com a OpenAI.
    """
    load_dotenv()
    prefs = _preferencias_llm()
    if not prefs:
        raise ValueError(
            "Nenhuma chave de LLM encontrada. Defina GROQ_API_KEY ou "
            "OPENAI_API_KEY no arquivo .env."
        )
    if url is not None:
        prefs["base_url"] = url
    if model is not None:
        prefs["model"] = model
    prefs.update(kwargs)
    return ChatOpenAI(**prefs)
