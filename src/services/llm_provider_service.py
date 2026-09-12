import os
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama
from src.services.bedrock_custom_adapter import CustomBedrockLLM
from dotenv import load_dotenv

GROQ_URL = "https://api.groq.com/openai/v1"
OPENAI_URL = "https://api.openai.com/v1"
OLLAMA_URL_PADRAO = "http://localhost:11434"
AWS_REGION_PADRAO = "us-east-1"

MODELO_GROQ = "qwen/qwen3.6-27b"
MODELO_OPENAI = "gpt-4o-mini"


def get_api_key(env_var_name: str = "GROQ_API_KEY") -> str | None:
    """Retorna a chave de API para o provedor LLM.

    Prioriza ``GROQ_API_KEY`` (padrão histórico), mas aceita ``OPENAI_API_KEY``
    como fallback — permitindo rodar a aplicação apenas com uma chave da OpenAI.
    Não se aplica ao provedor Ollama, que roda localmente sem chave de API.
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


def _preferencias_ollama() -> dict:
    """Kwargs para instanciar ``ChatOllama`` a partir do ambiente.

    Usa o cliente nativo do Ollama (não o modo compatível com OpenAI), então
    ``base_url`` é a raiz do servidor (ex.: ``http://localhost:11434``, sem
    sufixo ``/v1``).
    """
    modelo = os.getenv("MEDPT_OLLAMA_CHAT_MODEL", "").strip()
    if not modelo:
        raise ValueError(
            "MEDPT_LLM_PROVIDER=ollama exige MEDPT_OLLAMA_CHAT_MODEL definido "
            "no .env, com o nome do modelo importado no Ollama (o mesmo nome "
            "usado em 'ollama create <nome> -f Modelfile')."
        )
    return {
        "base_url": os.getenv("MEDPT_OLLAMA_BASE_URL", OLLAMA_URL_PADRAO) or OLLAMA_URL_PADRAO,
        "model": modelo,
    }


def _preferencias_bedrock() -> dict:
    """Kwargs para instanciar ``CustomBedrockLLM`` a partir do ambiente.

    Usa credenciais AWS do sistema (via boto3) — AWS_ACCESS_KEY_ID,
    AWS_SECRET_ACCESS_KEY, AWS_PROFILE, etc.

    Variáveis de ambiente:
    - MEDPT_BEDROCK_MODEL_ID: ID/ARN do modelo no Bedrock (obrigatório)
      Exemplos: "arn:aws:bedrock:us-east-1:651557246751:imported-model/5bsz71f67w1p"
    - MEDPT_BEDROCK_MODEL_PROVIDER: provider do modelo (informativo, não usado no adapter customizado)
    - AWS_REGION: região AWS (padrão: us-east-1)
    - AWS_PROFILE: perfil AWS (opcional, usa credenciais padrão se não informado)
    """
    model_id = os.getenv("MEDPT_BEDROCK_MODEL_ID", "").strip()
    if not model_id:
        raise ValueError(
            "MEDPT_LLM_PROVIDER=bedrock exige MEDPT_BEDROCK_MODEL_ID definido "
            "no .env com o ARN do modelo customizado no AWS Bedrock "
            "(ex.: 'arn:aws:bedrock:us-east-1:651557246751:imported-model/5bsz71f67w1p')"
        )

    region = os.getenv("AWS_REGION", AWS_REGION_PADRAO).strip() or AWS_REGION_PADRAO
    aws_profile = os.getenv("AWS_PROFILE", "").strip()

    prefs = {
        "model_id": model_id,
        "region_name": region,
    }

    if aws_profile:
        prefs["credentials_profile_name"] = aws_profile

    return prefs


def _preferencias_llm() -> dict:
    """Decide o provedor LLM a partir de ``MEDPT_LLM_PROVIDER`` ou, na ausência
    dele, das chaves/variáveis presentes no ambiente.

    Ordem quando ``MEDPT_LLM_PROVIDER`` não é informado: Bedrock > Groq > OpenAI > Ollama
    (Bedrock/Ollama entram apenas se explicitamente configurados ou quando nenhuma
    chave de nuvem (Groq/OpenAI) estiver presente).

    ``MEDPT_LLM_PROVIDER`` (valores: ``bedrock``, ``groq``, ``openai`` ou ``ollama``)
    força a escolha.

    Retorna um dicionário de kwargs prontos para instanciar o cliente do
    provedor escolhido, mais a chave interna ``_provedor`` (removida por
    ``get_llm`` antes de chamar o construtor — indica qual classe usar).
    """
    provedor_forcado = os.getenv("MEDPT_LLM_PROVIDER", "").strip().lower()
    groq = os.getenv("GROQ_API_KEY", "").strip()
    openai = os.getenv("OPENAI_API_KEY", "").strip()
    bedrock_model = os.getenv("MEDPT_BEDROCK_MODEL_ID", "").strip()

    if provedor_forcado == "bedrock":
        return {"_provedor": "bedrock", **_preferencias_bedrock()}

    if provedor_forcado == "ollama":
        return {"_provedor": "ollama", **_preferencias_ollama()}

    if provedor_forcado == "groq" and not groq:
        raise ValueError("MEDPT_LLM_PROVIDER=groq exige GROQ_API_KEY definido no .env.")
    if provedor_forcado == "openai" and not openai:
        raise ValueError("MEDPT_LLM_PROVIDER=openai exige OPENAI_API_KEY definido no .env.")

    if bedrock_model and provedor_forcado != "openai" and provedor_forcado != "groq":
        return {"_provedor": "bedrock", **_preferencias_bedrock()}

    if groq and provedor_forcado != "openai":
        return {
            "_provedor": "openai_compat",
            "api_key": groq,
            "base_url": os.getenv("MEDPT_LLM_BASE_URL", GROQ_URL) or GROQ_URL,
            "model": os.getenv("MEDPT_LLM_MODEL", MODELO_GROQ) or MODELO_GROQ,
            "reasoning_effort": os.getenv("MEDPT_LLM_REASONING_EFFORT") or "none",
        }
    if openai:
        return {
            "_provedor": "openai_compat",
            "api_key": openai,
            "base_url": os.getenv("MEDPT_LLM_BASE_URL", OPENAI_URL) or OPENAI_URL,
            "model": os.getenv("MEDPT_LLM_MODEL", MODELO_OPENAI) or MODELO_OPENAI,
        }
    if os.getenv("MEDPT_OLLAMA_CHAT_MODEL", "").strip():
        return {"_provedor": "ollama", **_preferencias_ollama()}
    return {}


def get_llm(
    url: str | None = None, model: str | None = None, **kwargs
) -> BaseChatModel:
    """Instancia o cliente de chat conforme o provedor configurado.

    Provedores suportados:
    - ``MEDPT_LLM_PROVIDER=bedrock``: AWS Bedrock com modelo customizado.
      Requer ``MEDPT_BEDROCK_MODEL_ID`` e credenciais AWS (boto3).
    - ``MEDPT_LLM_PROVIDER=ollama``: Ollama local — modelo customizado
      importado via ``ollama create``.
    - Com ``GROQ_API_KEY``: Groq (padrão com chave, com ``reasoning_effort``).
    - Com apenas ``OPENAI_API_KEY``: OpenAI (sem ``reasoning_effort``).

    Parâmetros e compatibilidade:
    - ``url``/``model`` (ou envs ``MEDPT_LLM_BASE_URL``/``MEDPT_LLM_MODEL``)
      permitem apontar Groq/OpenAI para qualquer provedor compatível com OpenAI.
    - Ollama usa ``MEDPT_OLLAMA_BASE_URL``/``MEDPT_OLLAMA_CHAT_MODEL``.
    - Bedrock usa ``AWS_REGION`` (padrão: us-east-1) e opcionalmente ``AWS_PROFILE``.

    Nota: parâmetros de limite de saída não são portáveis entre provedores.
    Groq/OpenAI usam ``max_tokens``; Ollama nativo usa ``num_predict``.
    """
    load_dotenv()
    prefs = _preferencias_llm()
    if not prefs:
        raise ValueError(
            "Nenhum provedor de LLM configurado. Configure um dos seguintes:\n"
            "- MEDPT_LLM_PROVIDER=bedrock + MEDPT_BEDROCK_MODEL_ID\n"
            "- MEDPT_LLM_PROVIDER=ollama + MEDPT_OLLAMA_CHAT_MODEL\n"
            "- GROQ_API_KEY (usa Groq por padrão)\n"
            "- OPENAI_API_KEY (usa OpenAI)"
        )

    provedor = prefs.pop("_provedor")

    if url is not None:
        prefs["base_url"] = url
    if model is not None:
        prefs["model"] = model
    prefs.update(kwargs)

    # Bedrock usa boto3 diretamente (não é compatível com LangChain de forma direta)
    if provedor == "bedrock":
        return CustomBedrockLLM(**prefs)

    if provedor == "ollama":
        return ChatOllama(**prefs)

    return ChatOpenAI(**prefs)
