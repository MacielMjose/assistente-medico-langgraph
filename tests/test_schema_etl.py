"""Testes do ETL e do schema sobre o PostgreSQL (banco de teste isolado)."""

from pathlib import Path

import pytest

from database.etl_seed import ResumoETL, rodar_etl
from src.db.buscar import BuscaRepositorio
from src.db.connection import conectar, contagem_por_tabela, violacoes_de_integridade
from src.db.models import EntradaLog
from src.db.repos import (
    AgendamentoRepositorio,
    AtendimentoRepositorio,
    EstatisticaRepositorio,
    LogRepositorio,
    PacienteRepositorio,
)

RAIZ = Path(__file__).resolve().parents[1]
PARQUET = RAIZ / "database" / "dataset_medpt_curado.parquet"

pytestmark = pytest.mark.pg

N_PACIENTES_MINI = 100
LIMITE_MINI = 3_000


@pytest.fixture(scope="module")
def mini_db(dsn_teste) -> str:
    resumo: ResumoETL = rodar_etl(
        caminho_parquet=PARQUET,
        dsn=dsn_teste,
        n_pacientes=N_PACIENTES_MINI,
        limite_linhas=LIMITE_MINI,
    )
    assert not resumo.avisos
    return dsn_teste


@pytest.fixture(scope="module")
def repos(mini_db) -> dict:
    return {
        "paciente": PacienteRepositorio(mini_db),
        "atendimento": AtendimentoRepositorio(mini_db),
        "agendamento": AgendamentoRepositorio(mini_db),
        "log": LogRepositorio(mini_db),
        "estatistica": EstatisticaRepositorio(mini_db),
        "busca": BuscaRepositorio(mini_db),
    }


def test_contagens_globais(mini_db: str):
    totais = contagem_por_tabela(mini_db)
    assert totais["pacientes"] == N_PACIENTES_MINI
    assert totais["atendimentos"] == LIMITE_MINI
    assert totais["profissionais"] > 0
    assert totais["condicoes"] > 0
    assert totais["especialidades"] > 0
    assert totais["exames"] > 0


def test_integridade_referencial(mini_db: str):
    assert violacoes_de_integridade(mini_db) == []


def test_dataset_refs_unicos_e_preservados(mini_db: str):
    with conectar(mini_db) as con:
        total, distintos, minimo = con.execute(
            "SELECT COUNT(*) AS total, COUNT(DISTINCT dataset_ref) AS distintos, "
            "MIN(dataset_ref) AS minimo FROM atendimentos"
        ).fetchone().values()
    assert total == distintos == LIMITE_MINI
    assert minimo >= 0


def test_historicos_distribuidos(repos: dict):
    com_historico = 0
    atendimento = repos["atendimento"]
    for pid in range(1, N_PACIENTES_MINI + 1):
        if len(atendimento.obter_prontuarios(pid)) >= 2:
            com_historico += 1
    assert com_historico >= N_PACIENTES_MINI // 2


def test_datas_de_atendimento_validas(mini_db: str):
    with conectar(mini_db) as con:
        futuras, nascidos_tarde = con.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM atendimentos WHERE data_atendimento > now()) AS futuras,
                (SELECT COUNT(*) FROM pacientes WHERE data_nascimento > CURRENT_DATE) AS nascidos_tarde
            """
        ).fetchone().values()
    assert futuras == 0
    assert nascidos_tarde == 0


def test_paciente_condicao_consistente_com_atendimentos(mini_db: str):
    with conectar(mini_db) as con:
        divergentes, status_invalidos = con.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM (
                    SELECT DISTINCT paciente_id, condicao_id FROM atendimentos
                    EXCEPT
                    SELECT paciente_id, condicao_id FROM paciente_condicao
                ) divergencia) AS divergentes,
                (SELECT COUNT(*) FROM paciente_condicao
                 WHERE status NOT IN ('ativo', 'cronico', 'resolvido')) AS status_invalidos
            """
        ).fetchone().values()
    assert divergentes == 0
    assert status_invalidos == 0


def test_busca_textual_hibrida_populada(mini_db: str, repos: dict):
    resultados = repos["busca"].buscar_texto("dor", limite=5)
    assert resultados
    for resultado in resultados:
        assert resultado.atendimento_id > 0
        assert resultado.condicao


def test_especialidades_multiplas_normalizadas(mini_db: str):
    with conectar(mini_db) as con:
        nomes_com_virgula, vinculados_ok = con.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM especialidades WHERE nome LIKE '%,%') AS nomes_com_virgula,
                (SELECT COUNT(*) FROM profissional_especialidade pe
                 JOIN especialidades e ON e.id = pe.especialidade_id) AS vinculados_ok
            """
        ).fetchone().values()
    assert nomes_com_virgula == 0
    assert vinculados_ok > 0


def test_fluxo_do_grafo(mini_db: str, repos: dict):
    estatisticas = repos["estatistica"].estatisticas()
    assert estatisticas.atendimentos == LIMITE_MINI

    pacientes = repos["paciente"].buscar_paciente("a", limite=3)
    assert 0 < len(pacientes) <= 3
    alvo = pacientes[0]

    prontuarios = repos["atendimento"].obter_prontuarios(alvo.id)
    datas = [p.data_atendimento for p in prontuarios]
    assert datas == sorted(datas, reverse=True)

    condicoes = repos["atendimento"].obter_condicoes(alvo.id)
    assert all(c.status in ("ativo", "cronico", "resolvido") for c in condicoes)

    exames = repos["atendimento"].obter_exames(alvo.id)
    assert all(e.paciente_id == alvo.id for e in exames)

    log_id = repos["log"].registrar_log(
        EntradaLog(sessao_id="sessao-teste", acao="consulta_prontuario", detalhe={"paciente": alvo.id})
    )
    assert log_id > 0
    with conectar(mini_db) as con:
        detalhe = con.execute(
            "SELECT detalhe FROM log_auditoria WHERE id = %s", (log_id,)
        ).fetchone()["detalhe"]
    assert detalhe["paciente"] == alvo.id


def test_inexistente_retorna_vazio(repos: dict):
    assert repos["paciente"].obter_paciente(999_999_999) is None
    assert repos["atendimento"].obter_prontuarios(999_999_999) == []
    assert repos["paciente"].buscar_paciente("QWERTYUIOP_INEXISTENTE") == []


def test_agendamentos_gerados(mini_db: str, repos: dict):
    assert repos["estatistica"].estatisticas().agendamentos > 0


def test_agendamentos_status_validos(mini_db: str):
    with conectar(mini_db) as con:
        invalidos = con.execute(
            """
            SELECT COUNT(*) FROM agendamentos
            WHERE status NOT IN ('agendada', 'confirmada', 'realizada', 'cancelada', 'nao_compareceu')
            """
        ).fetchone()["count"]
    assert invalidos == 0


def test_agendamentos_fk_validas(mini_db: str):
    assert violacoes_de_integridade(mini_db) == []


def test_repository_agendamentos(repos: dict):
    pacientes = repos["paciente"].buscar_paciente("a", limite=1)
    if pacientes:
        agendamentos = repos["agendamento"].obter_agendamentos(pacientes[0].id)
        assert isinstance(agendamentos, list)
        if agendamentos:
            assert agendamentos[0].paciente_id == pacientes[0].id


def test_agendamento_periodo_e_status(repos: dict):
    agendamentos = repos["agendamento"].obter_agendamentos_por_periodo(
        "2000-01-01", "2100-01-01", status="realizada"
    )
    assert agendamentos
    assert all(a.status == "realizada" for a in agendamentos)