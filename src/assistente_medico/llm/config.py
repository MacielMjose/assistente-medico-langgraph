import os
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv


def get_api_key(env_var_name: str = "OPENAI_API_KEY") -> str | None:
    load_dotenv()
    api_key = os.getenv(env_var_name)
    if api_key is None or api_key == "":
        raise ValueError(f"{env_var_name} não encontrado no arquivo .env")
    return api_key


def get_llm(
    url: str = "https://api.groq.com/openai/v1", model: str = "qwen/qwen3.6-27b"
) -> ChatOpenAI:
    llm = ChatOpenAI(
        model=model,
        base_url=url,
        api_key=get_api_key(),
        reasoning_effort="none",
    )
    return llm
