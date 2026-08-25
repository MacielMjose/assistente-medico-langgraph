import sqlite3
from pathlib import Path

import pytest

from database.etl_seed import ResumoETL, rodar_etl
from src.db.models import EntradaLog
from src.db.repository import RepositorioClinico

RAIZ = Path(__file__).resolve().parents[1]
PARQUET = RAIZ / "database" / "dataset_medpt_curado.parquet"

pytestmark = pytest.mark.skipif(not PARQUET.exists(), reason="parquet não encontrado")

N_PACIENTES_MINI = 100
LIMITE_MINI = 3_000


@pytest.fixture(scope="module")
def mini_db(tmp_path_factory) -> Path:
    caminho = tmp_path_factory.mktemp("mini") / "mini.db"
    resumo: ResumoETL = rodar_etl(
        caminho_parquet=PARQUET,
        caminho_db=caminho,
        n_pacientes=N_PACIENTES_MINI,
        limite_linhas=LIMITE_MINI,
    )
    assert not resumo.avisos
    return caminho


@pytest.fixture(scope="module")
def repositorio(mini_db: Path) -> RepositorioClinico:
    return RepositorioClinico(mini_db)


def test_contagens_globais(mini_db: Path):
    con = sqlite3.connect(mini_db)
    estat = dict(
        zip(
            [col[0] for col in con.execute("SELECT * FROM vw_estatisticas_base").description],
            con.execute("SELECT * FROM vw_estatisticas_base").fetchone(),
        )
    )
    con.close()
    assert estat["pacientes"] == N_PACIENTES_MINI
    assert estat["atendimentos"] == LIMITE_MINI
    assert estat["profissionais"] > 0
    assert estat["condicoes"] > 0
    assert estat["especialidades"] > 0
    assert estat["exames"] > 0


def test_integridade_referencial(mini_db: Path):
    con = sqlite3.connect(mini_db)
    assert con.execute("PRAGMA foreign_key_check").fetchall() == []
    orfaos = con.execute(
        """
        SELECT COUNT(*) FROM atendimentos a
        LEFT JOIN pacientes p ON p.id = a.paciente_id
        WHERE p.id IS NULL
        """
    ).fetchone()[0]
    con.close()
    assert orfaos == 0


def test_dataset_refs_unicos_e_preservados(mini_db: Path):
    con = sqlite3.connect(mini_db)
    total, distintos = con.execute(
        "SELECT COUNT(*), COUNT(DISTINCT dataset_ref) FROM atendimentos"
    ).fetchone()
    minimo = con.execute("SELECT MIN(dataset_ref) FROM atendimentos").fetchone()[0]
    con.close()
    assert total == distintos == LIMITE_MINI
    assert minimo >= 0


def test_historicos_distribuidos(repositorio: RepositorioClinico):
    com_historico = 0
    for pid in range(1, N_PACIENTES_MINI + 1):
        if len(repositorio.obter_prontuarios(pid)) >= 2:
            com_historico += 1
    assert com_historico >= N_PACIENTES_MINI // 2


def test_datas_de_atendimento_validas(mini_db: Path):
    con = sqlite3.connect(mini_db)
    futuras, nascidos_tarde = con.execute(
        """
        SELECT
            (SELECT COUNT(*) FROM atendimentos WHERE date(data_atendimento) > date('now')),
            (SELECT COUNT(*) FROM pacientes WHERE data_nascimento > date('now'))
        """
    ).fetchone()
    con.close()
    assert futuras == 0
    assert nascidos_tarde == 0


def test_paciente_condicao_consistente_com_atendimentos(mini_db: Path):
    con = sqlite3.connect(mini_db)
    divergentes = con.execute(
        """
        SELECT COUNT(*) FROM (
            SELECT DISTINCT paciente_id, condicao_id FROM atendimentos
            EXCEPT
            SELECT paciente_id, condicao_id FROM paciente_condicao
        )
        """
    ).fetchone()[0]
    status_invalidos = con.execute(
        "SELECT COUNT(*) FROM paciente_condicao WHERE status NOT IN ('ativo','cronico','resolvido')"
    ).fetchone()[0]
    con.close()
    assert divergentes == 0
    assert status_invalidos == 0


def test_fts_populado_e_busca_funciona(mini_db: Path):
    con = sqlite3.connect(mini_db)
    fts, tabela = con.execute(
        "SELECT (SELECT COUNT(*) FROM atendimentos_fts), (SELECT COUNT(*) FROM atendimentos)"
    ).fetchone()
    con.close()
    assert fts == tabela

    repo = RepositorioClinico(mini_db)
    resultados = repo.buscar_texto("dor", limite=5)
    for resultado in resultados:
        assert resultado.atendimento_id > 0
        assert resultado.condicao


def test_especialidades_multiplas_normalizadas(mini_db: Path):
    con = sqlite3.connect(mini_db)
    nomes_com_virgula = con.execute(
        "SELECT COUNT(*) FROM especialidades WHERE nome LIKE '%,%'"
    ).fetchone()[0]
    vinculados_ok = con.execute(
        """
        SELECT COUNT(*) FROM profissional_especialidade pe
        JOIN especialidades e ON e.id = pe.especialidade_id
        """
    ).fetchone()[0]
    con.close()
    assert nomes_com_virgula == 0
    assert vinculados_ok > 0


def test_repository_fluxo_do_grafo(repositorio: RepositorioClinico):
    estatisticas = repositorio.estatisticas()
    assert estatisticas.atendimentos == LIMITE_MINI

    pacientes = repositorio.buscar_paciente("a", limite=3)
    assert 0 < len(pacientes) <= 3
    alvo = pacientes[0]

    prontuarios = repositorio.obter_prontuarios(alvo.id)
    datas = [p.data_atendimento for p in prontuarios]
    assert datas == sorted(datas, reverse=True)

    condicoes = repositorio.obter_condicoes(alvo.id)
    assert all(c.status in ("ativo", "cronico", "resolvido") for c in condicoes)

    exames = repositorio.obter_exames(alvo.id)
    assert all(e.paciente_id == alvo.id for e in exames)

    log_id = repositorio.registrar_log(
        EntradaLog(sessao_id="sessao-teste", acao="consulta_prontuario", detalhe={"paciente": alvo.id})
    )
    assert log_id > 0

    import json
    import sqlite3 as s3

    con = s3.connect(repositorio._caminho_db)
    detalhe = con.execute("SELECT detalhe FROM log_auditoria WHERE id = ?", (log_id,)).fetchone()[0]
    con.close()
    assert json.loads(detalhe)["paciente"] == alvo.id


def test_inexistente_retorna_vazio(repositorio: RepositorioClinico):
    assert repositorio.obter_paciente(999_999_999) is None
    assert repositorio.obter_prontuarios(999_999_999) == []
    assert repositorio.buscar_paciente("QWERTYUIOP_INEXISTENTE") == []


def test_agendamentos_gerados(mini_db: Path):
    con = sqlite3.connect(mini_db)
    total = con.execute("SELECT COUNT(*) FROM agendamentos").fetchone()[0]
    con.close()
    assert total > 0


def test_agendamentos_status_validos(mini_db: Path):
    con = sqlite3.connect(mini_db)
    invalidos = con.execute(
        """
        SELECT COUNT(*) FROM agendamentos 
        WHERE status NOT IN ('agendada', 'confirmada', 'realizada', 'cancelada', 'nao_compareceu')
        """
    ).fetchone()[0]
    con.close()
    assert invalidos == 0


def test_agendamentos_fk_validas(mini_db: Path):
    con = sqlite3.connect(mini_db)
    assert con.execute("PRAGMA foreign_key_check").fetchall() == []
    con.close()


def test_repository_agendamentos(repositorio: RepositorioClinico):
    pacientes = repositorio.buscar_paciente("a", limite=1)
    if pacientes:
        agendamentos = repositorio.obter_agendamentos(pacientes[0].id)
        assert isinstance(agendamentos, list)
        if agendamentos:
            assert agendamentos[0].paciente_id == pacientes[0].id


def test_estatisticas_inclui_agendamentos(mini_db: Path):
    con = sqlite3.connect(mini_db)
    colunas = [col[0] for col in con.execute("SELECT * FROM vw_estatisticas_base").description]
    con.close()
    assert "agendamentos" in colunas
