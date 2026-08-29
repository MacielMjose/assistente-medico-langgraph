"""Fixtures compartilhadas para os testes de integração com PostgreSQL.

Todos os testes marcados com ``@pytest.mark.pg`` exigem o container no ar e a
variável ``MEDPT_TESTAR_PG=1``; caso contrário, são pulados automaticamente.
"""

import os

import psycopg
import pytest

DSN_PADRAO = "postgresql://medico:medico_dev@localhost:5433/assistente_medico"
DB_DE_TESTE = "assistente_medico_test"


def _url_administrador() -> str:
    dsn = os.getenv("MEDPT_PG_DSN", DSN_PADRAO)
    base, _, _banco = dsn.rpartition("/")
    return f"{base}/postgres"


def _criar_banco(nome: str) -> str:
    url = _url_administrador()
    with psycopg.connect(url, autocommit=True) as con:
        con.execute(f'DROP DATABASE IF EXISTS {nome} WITH (FORCE)')
        con.execute(f'CREATE DATABASE {nome}')
    base = url.rpartition("/")[0]
    dsn = f"{base}/{nome}"
    with psycopg.connect(dsn, autocommit=True) as con:
        con.execute("CREATE EXTENSION IF NOT EXISTS vector")
    return dsn


def _dropar_banco(nome: str) -> None:
    with psycopg.connect(_url_administrador(), autocommit=True) as con:
        con.execute(f'DROP DATABASE IF EXISTS {nome} WITH (FORCE)')


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "pg: testes de integração contra o PostgreSQL em container (MEDPT_TESTAR_PG=1)",
    )


def pytest_runtest_setup(item):
    if "pg" in item.keywords and os.getenv("MEDPT_TESTAR_PG") != "1":
        pytest.skip("defina MEDPT_TESTAR_PG=1 com o container PostgreSQL no ar")


@pytest.fixture(scope="session")
def dsn_teste():
    """Banco dedicado de teste, recriado a cada sessão."""
    dsn = _criar_banco(DB_DE_TESTE)
    yield dsn
    _dropar_banco(DB_DE_TESTE)


@pytest.fixture
def criar_banco_isolado():
    criados: list[str] = []

    def _criar() -> str:
        nome = f"test_isolado_{len(criados)}"
        criados.append(nome)
        return _criar_banco(nome)

    yield _criar
    for nome in criados:
        _dropar_banco(nome)