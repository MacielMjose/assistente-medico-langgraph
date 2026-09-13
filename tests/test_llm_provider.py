"""Testes unitários do provedor de LLM (seleção Groq/OpenAI/Ollama).

Não exige banco de dados nem chamadas reais de rede: apenas monta a
instância do cliente (ChatOpenAI ou ChatOllama) e confere a escolha do
provedor conforme as variáveis de ambiente presentes.
"""

import pytest

from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama

from src.services.llm_provider_service import get_api_key, get_llm


def _limpar_env(monkeypatch):
    """Zera as variáveis de LLM (load_dotenv usa setdefault; esvaziar > deletar)."""
    for var in (
        "GROQ_API_KEY", "OPENAI_API_KEY", "MEDPT_LLM_BASE_URL",
        "MEDPT_LLM_MODEL", "MEDPT_LLM_REASONING_EFFORT", "MEDPT_LLM_PROVIDER",
        "MEDPT_OLLAMA_CHAT_MODEL", "MEDPT_OLLAMA_BASE_URL",
    ):
        monkeypatch.setenv(var, "")


def test_get_llm_usa_groq_quando_chave_esta_presente(monkeypatch):
    _limpar_env(monkeypatch)
    monkeypatch.setenv("GROQ_API_KEY", "groq_teste")
    llm = get_llm()
    assert isinstance(llm, ChatOpenAI)
    assert llm.openai_api_base == "https://api.groq.com/openai/v1"
    assert llm.model_name == "qwen/qwen3.6-27b"
    assert bool(llm.openai_api_key)
    assert llm.reasoning_effort == "none"


def test_get_llm_usa_openai_apenas_com_openai_key(monkeypatch):
    _limpar_env(monkeypatch)
    monkeypatch.setenv("OPENAI_API_KEY", "openai_teste")
    llm = get_llm()
    assert isinstance(llm, ChatOpenAI)
    assert llm.openai_api_base == "https://api.openai.com/v1"
    assert llm.model_name == "gpt-4o-mini"
    assert bool(llm.openai_api_key)
    assert llm.reasoning_effort is None


def test_get_llm_prioriza_groq_quando_ambas_existem(monkeypatch):
    _limpar_env(monkeypatch)
    monkeypatch.setenv("GROQ_API_KEY", "groq_teste")
    monkeypatch.setenv("OPENAI_API_KEY", "openai_teste")
    llm = get_llm()
    assert bool(llm.openai_api_key)
    assert "groq.com" in llm.openai_api_base


def test_get_llm_sem_nenhum_provedor_levanta_erro(monkeypatch):
    _limpar_env(monkeypatch)
    with pytest.raises(ValueError, match="GROQ_API_KEY.*OPENAI_API_KEY.*MEDPT_OLLAMA_CHAT_MODEL"):
        get_llm()


def test_get_llm_respeita_overrides_de_ambiente(monkeypatch):
    _limpar_env(monkeypatch)
    monkeypatch.setenv("GROQ_API_KEY", "groq_teste")
    monkeypatch.setenv("MEDPT_LLM_BASE_URL", "https://vllm.local/v1")
    monkeypatch.setenv("MEDPT_LLM_MODEL", "meu-modelo")
    llm = get_llm()
    assert llm.openai_api_base == "https://vllm.local/v1"
    assert llm.model_name == "meu-modelo"


def test_get_api_key_fallbacks_para_openai(monkeypatch):
    _limpar_env(monkeypatch)
    monkeypatch.setenv("OPENAI_API_KEY", "openai_teste")
    assert get_api_key() == "openai_teste"


def test_get_api_key_prioriza_groq(monkeypatch):
    _limpar_env(monkeypatch)
    monkeypatch.setenv("GROQ_API_KEY", "groq_teste")
    monkeypatch.setenv("OPENAI_API_KEY", "openai_teste")
    assert get_api_key() == "groq_teste"


def test_get_api_key_sem_chave_levanta_erro(monkeypatch):
    _limpar_env(monkeypatch)
    with pytest.raises(ValueError, match="Nenhuma chave"):
        get_api_key()


# ---------------------------------------------------------------------------
# Ollama (modelo customizado local)
# ---------------------------------------------------------------------------

def test_get_llm_usa_ollama_automaticamente_sem_chave_de_nuvem(monkeypatch):
    _limpar_env(monkeypatch)
    monkeypatch.setenv("MEDPT_OLLAMA_CHAT_MODEL", "meu-modelo-medico")
    llm = get_llm()
    assert isinstance(llm, ChatOllama)
    assert llm.model == "meu-modelo-medico"
    assert llm.base_url == "http://localhost:11434"


def test_get_llm_ollama_respeita_base_url_customizada(monkeypatch):
    _limpar_env(monkeypatch)
    monkeypatch.setenv("MEDPT_OLLAMA_CHAT_MODEL", "meu-modelo-medico")
    monkeypatch.setenv("MEDPT_OLLAMA_BASE_URL", "http://ollama:11434")
    llm = get_llm()
    assert llm.base_url == "http://ollama:11434"


def test_get_llm_provider_ollama_forca_local_mesmo_com_chaves_de_nuvem(monkeypatch):
    _limpar_env(monkeypatch)
    monkeypatch.setenv("GROQ_API_KEY", "groq_teste")
    monkeypatch.setenv("OPENAI_API_KEY", "openai_teste")
    monkeypatch.setenv("MEDPT_LLM_PROVIDER", "ollama")
    monkeypatch.setenv("MEDPT_OLLAMA_CHAT_MODEL", "meu-modelo-medico")
    llm = get_llm()
    assert isinstance(llm, ChatOllama)
    assert llm.model == "meu-modelo-medico"


def test_get_llm_provider_ollama_sem_modelo_levanta_erro(monkeypatch):
    _limpar_env(monkeypatch)
    monkeypatch.setenv("MEDPT_LLM_PROVIDER", "ollama")
    with pytest.raises(ValueError, match="MEDPT_OLLAMA_CHAT_MODEL"):
        get_llm()


def test_get_llm_provider_groq_sem_chave_levanta_erro(monkeypatch):
    _limpar_env(monkeypatch)
    monkeypatch.setenv("MEDPT_LLM_PROVIDER", "groq")
    with pytest.raises(ValueError, match="GROQ_API_KEY"):
        get_llm()


def test_get_llm_provider_openai_forca_mesmo_com_groq_presente(monkeypatch):
    _limpar_env(monkeypatch)
    monkeypatch.setenv("GROQ_API_KEY", "groq_teste")
    monkeypatch.setenv("OPENAI_API_KEY", "openai_teste")
    monkeypatch.setenv("MEDPT_LLM_PROVIDER", "openai")
    llm = get_llm()
    assert isinstance(llm, ChatOpenAI)
    assert llm.model_name == "gpt-4o-mini"
