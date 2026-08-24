"""Testes de integração contra a base completa (database/assistente_medico.db).

São pulados automaticamente se a base completa ainda não foi gerada:
    python database/etl_seed.py
"""

import sqlite3
from pathlib import Path

import pytest

from src.db.repository import RepositorioClinico

RAIZ = Path(__file__).resolve().parents[1]
DB_COMPLETO = RAIZ / "database" / "assistente_medico.db"

TOTAL_ESPERADO = 384_084
N_PACIENTES_PADRAO = 10_000

pytestmark = pytest.mark.skipif(not DB_COMPLETO.exists(), reason="base completa não gerada")


@pytest.fixture(scope="module")
def repo() -> RepositorioClinico:
    return RepositorioClinico(DB_COMPLETO)


def test_carga_completa():
    con = sqlite3.connect(DB_COMPLETO)
    estat = con.execute("SELECT * FROM vw_estatisticas_base").fetchone()
    violacoes = con.execute("PRAGMA foreign_key_check").fetchall()
    con.close()
    pacientes, profissionais, atendimentos, condicoes, especialidades, exames, _ = estat
    assert atendimentos == TOTAL_ESPERADO
    assert pacientes == N_PACIENTES_PADRAO
    assert profissionais > 0 and condicoes > 0 and especialidades > 0 and exames > 0
    assert violacoes == []


def test_fts_cobertura_total():
    con = sqlite3.connect(DB_COMPLETO)
    fts, tabela = con.execute(
        "SELECT (SELECT COUNT(*) FROM atendimentos_fts), (SELECT COUNT(*) FROM atendimentos)"
    ).fetchone()
    con.close()
    assert fts == tabela == TOTAL_ESPERADO


def test_busca_hibrida_com_filtro(repo: RepositorioClinico):
    resultados = repo.buscar_texto("dor lombar", condicao="Hérnia Inguinal", limite=5)
    for resultado in resultados[:5]:
        assert resultado.condicao == "Hérnia Inguinal"


def test_historico_tipico_do_paciente(repo: RepositorioClinico):
    paciente = repo.buscar_paciente("a", limite=1)[0]
    prontuarios = repo.obter_prontuarios(paciente.id, limite=50)
    condicoes = repo.obter_condicoes(paciente.id)
    assert len(prontuarios) >= 2
    datas = [p.data_atendimento for p in prontuarios]
    assert datas == sorted(datas, reverse=True)
    menor_diagnostico = min(c.data_diagnostico for c in condicoes)
    assert all(p.data_atendimento.date() >= menor_diagnostico for p in prontuarios)
