"""Integração contra a base completa PostgreSQL (banco de dev).

Requer o container no ar, a carga completa e a ingestão de embeddings:
    docker compose -f docker-compose.yml up -d
    python database/etl_seed.py
    python database/embeddings_ingest.py --provider mock --limite 50000

Sem o container, os testes são pulados automaticamente (marcador ``pg``).
"""

import pytest

from src.db.buscar import BuscaRepositorio
from src.db.connection import contagem_por_tabela, violacoes_de_integridade
from src.db.embeddings import obter_provedor
from src.db.models import EntradaLog
from src.db.repos import (
    AtendimentoRepositorio,
    EstatisticaRepositorio,
    LogRepositorio,
    PacienteRepositorio,
)

pytestmark = pytest.mark.pg

TOTAL_ESPERADO = 384_084
N_PACIENTES_PADRAO = 10_000


@pytest.fixture(scope="module")
def repos() -> dict:
    return {
        "paciente": PacienteRepositorio(),
        "atendimento": AtendimentoRepositorio(),
        "log": LogRepositorio(),
        "estatistica": EstatisticaRepositorio(),
        "busca": BuscaRepositorio(),
    }


def test_carga_completa(repos: dict):
    totais = contagem_por_tabela()
    assert totais["atendimentos"] == TOTAL_ESPERADO
    assert totais["pacientes"] == N_PACIENTES_PADRAO
    assert totais["profissionais"] > 0
    assert totais["condicoes"] > 0
    assert totais["especialidades"] > 0
    assert totais["exames"] > 0
    assert violacoes_de_integridade() == []


def test_estatisticas_consistem_com_tabelas(repos: dict):
    estat = repos["estatistica"].estatisticas()
    assert estat.atendimentos == TOTAL_ESPERADO
    assert estat.pacientes == N_PACIENTES_PADRAO


def test_busca_textual_portugues_com_filtro(repos: dict):
    resultados = repos["busca"].buscar_texto(
        "dor lombar", condicao="Hérnia Inguinal", limite=5
    )
    for resultado in resultados[:5]:
        assert resultado.condicao == "Hérnia Inguinal"


def test_fluxo_paciente(repos: dict):
    pacientes = repos["paciente"].buscar_paciente("Maria", limite=2)
    assert pacientes
    alvo = repos["paciente"].obter_paciente(pacientes[0].id)
    assert alvo.nome == pacientes[0].nome
    prontuarios = repos["atendimento"].obter_prontuarios(alvo.id, limite=50)
    datas = [p.data_atendimento for p in prontuarios]
    assert datas == sorted(datas, reverse=True)
    condicoes = repos["atendimento"].obter_condicoes(alvo.id)
    menor_diagnostico = min(c.data_diagnostico for c in condicoes)
    assert all(p.data_atendimento.date() >= menor_diagnostico for p in prontuarios)


def test_busca_vetorial_hnsw(repos: dict):
    provedor = obter_provedor("mock")
    resultados = repos["busca"].buscar_vetorial(
        "dor lombar ao levantar peso", provedor, k=5
    )
    if not resultados:
        pytest.skip(
            "nenhum chunk ingestado na base dev ainda; rode database/embeddings_ingest.py"
        )
    similaridades = [r.similaridade for r in resultados]
    assert similaridades == sorted(similaridades, reverse=True)
    assert all(-1.0 <= s <= 1.0 for s in similaridades)


def test_log_jsonb(repos: dict):
    log_id = repos["log"].registrar_log(
        EntradaLog(sessao_id="teste-pg", acao="smoke", detalhe={"origem": "pytest"})
    )
    assert log_id > 0