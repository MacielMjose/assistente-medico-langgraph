"""Testes unitários do provedor de LLM (seleção Groq/OpenAI).

Não exige banco de dados nem chamadas reais de rede: apenas monta a instância
ChatOpenAI e confere a escolha do provedor conforme as chaves presentes no
ambiente.
"""

import pytest

from src.services.llm_provider_service import get_api_key, get_llm


def _limpar_env(monkeypatch):
    """Zera as variáveis de LLM (load_dotenv usa setdefault; esvaziar > deletar)."""
    for var in ("GROQ_API_KEY", "OPENAI_API_KEY", "MEDPT_LLM_BASE_URL",
                "MEDPT_LLM_MODEL", "MEDPT_LLM_REASONING_EFFORT"):
        monkeypatch.setenv(var, "")


def test_get_llm_usa_groq_quando_chave_esta_presente(monkeypatch):
    _limpar_env(monkeypatch)
    monkeypatch.setenv("GROQ_API_KEY", "groq_teste")
    llm = get_llm()
    assert llm.openai_api_base == "https://api.groq.com/openai/v1"
    assert llm.model_name == "qwen/qwen3.6-27b"
    assert bool(llm.openai_api_key)
    assert llm.reasoning_effort == "none"


def test_get_llm_usa_openai_apenas_com_openai_key(monkeypatch):
    _limpar_env(monkeypatch)
    monkeypatch.setenv("OPENAI_API_KEY", "openai_teste")
    llm = get_llm()
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


def test_get_llm_sem_chave_levanta_erro(monkeypatch):
    _limpar_env(monkeypatch)
    with pytest.raises(ValueError, match="GROQ_API_KEY ou OPENAI_API_KEY"):
        get_llm()


def test_get_llm_respeita_overrides_de_ambiente(monkeypatch):
    _limpar_env(monkeypatch)
    monkeypatch.setenv("GROQ_API_KEY", "groq_teste")
    monkeypatch.setenv("MEDPT_LLM_BASE_URL", "https://ollama.local/v1")
    monkeypatch.setenv("MEDPT_LLM_MODEL", "meu-modelo")
    llm = get_llm()
    assert llm.openai_api_base == "https://ollama.local/v1"
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