"""Testes de integração contra o Postgres+pgvector (Fase B).

Requer o container no ar e a base migrada:
    docker compose up -d
    python database/migrate_sqlite_to_pg.py

Sem o container, todos os testes são pulados automaticamente.
"""

import os

import pytest

from src.db.embeddings import EmbeddingsMock
from src.db.repository_pg import RepositorioClinicoPg

DSN = os.getenv("MEDPT_PG_DSN", "postgresql://medico:medico_dev@localhost:5433/assistente_medico")

pytestmark = pytest.mark.skipif(
    os.getenv("MEDPT_TESTAR_PG") != "1", reason="defina MEDPT_TESTAR_PG=1 com o container no ar"
)


@pytest.fixture(scope="module")
def repo() -> RepositorioClinicoPg:
    return RepositorioClinicoPg(DSN)


def test_estatisticas_carregadas(repo: RepositorioClinicoPg):
    estat = repo.estatisticas()
    assert estat.atendimentos > 0
    assert estat.pacientes > 0


def test_busca_textual_portugues(repo: RepositorioClinicoPg):
    resultados = repo.buscar_texto("dor de cabeça", limite=3)
    assert 0 < len(resultados) <= 3
    assert all(r.relevancia >= 0 for r in resultados)


def test_fluxo_paciente(repo: RepositorioClinicoPg):
    pacientes = repo.buscar_paciente("Maria", limite=2)
    assert pacientes
    alvo = repo.obter_paciente(pacientes[0].id)
    assert alvo.nome == pacientes[0].nome
    prontuarios = repo.obter_prontuarios(alvo.id, limite=5)
    datas = [p.data_atendimento for p in prontuarios]
    assert datas == sorted(datas, reverse=True)


def _provedor_compativel():
    try:
        from src.db.embeddings import EmbeddingsE5Local

        return EmbeddingsE5Local()
    except (ImportError, RuntimeError, OSError):
        return EmbeddingsMock()


def test_busca_vetorial_hnsw(repo: RepositorioClinicoPg):
    provedor = _provedor_compativel()
    resultados = repo.buscar_vetorial("dor lombar ao levantar peso", provedor, k=5)
    if not resultados:
        pytest.skip("nenhum chunk embutido na base pg ainda")
    similaridades = [r.similaridade for r in resultados]
    assert similaridades == sorted(similaridades, reverse=True)
    assert all(-1.0 <= s <= 1.0 for s in similaridades)


def test_log_jsonb(repo: RepositorioClinicoPg):
    from src.db.models import EntradaLog

    log_id = repo.registrar_log(
        EntradaLog(sessao_id="teste-pg", acao="smoke", detalhe={"origem": "pytest"})
    )
    assert log_id > 0
