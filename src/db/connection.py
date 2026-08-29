"""Conexão com o PostgreSQL (17 + pgvector) via psycopg 3.

O projeto inteiro roda sobre PostgreSQL+pgvector em container Docker
(docker-compose.yml na raiz). Nenhuma instância SQLite é usada.

Uso:
    with sessao() as con:
        con.execute("SELECT count(*) FROM pacientes")
"""

import os
from contextlib import contextmanager
from pathlib import Path

import psycopg
from pgvector.psycopg import register_vector
from psycopg.rows import dict_row

DSN_PADRAO = "postgresql://medico:medico_dev@localhost:5433/assistente_medico"

RAIZ_PROJETO = Path(__file__).resolve().parents[2]
SCRIPTS_POSTGRES_DIR = RAIZ_PROJETO / "database" / "scripts" / "postgres"

TABELAS_RELEVANTES = (
    "especialidades",
    "condicoes",
    "tipos_questao",
    "profissionais",
    "profissional_especialidade",
    "pacientes",
    "paciente_condicao",
    "atendimentos",
    "exames",
    "agendamentos",
    "log_auditoria",
)


def resolver_dsn(dsn: str | None = None) -> str:
    return dsn or os.getenv("MEDPT_PG_DSN", DSN_PADRAO)


def conectar(dsn: str | None = None) -> psycopg.Connection:
    """Abre conexão psycopg com linhas como dict e tipos vetoriais registrados."""

    conexao = psycopg.connect(resolver_dsn(dsn), row_factory=dict_row)
    register_vector(conexao)
    return conexao


@contextmanager
def sessao(dsn: str | None = None):
    conexao = conectar(dsn)
    try:
        yield conexao
    finally:
        conexao.close()


def aplicar_schema(dsn: str | None = None, caminho_scripts: str | Path | None = None) -> None:
    """Executa todos os scripts *.sql de database/scripts/postgres em ordem."""

    diretorio = Path(caminho_scripts) if caminho_scripts else SCRIPTS_POSTGRES_DIR
    with conectar(dsn) as conexao:
        for arquivo in sorted(diretorio.glob("*.sql")):
            conexao.execute(arquivo.read_text(encoding="utf-8"))
        conexao.commit()


def recriar_schema(dsn: str | None = None) -> None:
    """Apaga toda a estrutura do schema public e recria pelos scripts.

    Remove também as tabelas criadas pelo vector store do LangChain
    (langchain_pg_collection / langchain_pg_embedding), garantindo partida limpa.
    As views dependentes são removidas em cascata pelo DROP TABLE.
    """

    with conectar(dsn) as conexao:
        tabelas = conexao.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
        ).fetchall()
        for tabela in tabelas:
            conexao.execute(f'DROP TABLE IF EXISTS public."{tabela["tablename"]}" CASCADE')
        conexao.commit()
    aplicar_schema(dsn)


def contagem_por_tabela(dsn: str | None = None) -> dict[str, int]:
    """Contagem de linhas de cada tabela relevante (para verificação/bateria de testes)."""

    totais: dict[str, int] = {}
    with conectar(dsn) as conexao:
        for tabela in TABELAS_RELEVANTES:
            totais[tabela] = conexao.execute(
                "SELECT count(*) FROM information_schema.tables "
                "WHERE table_schema='public' AND table_name=%s",
                (tabela,),
            ).fetchone()["count"]
            if totais[tabela]:
                totais[tabela] = conexao.execute(
                    f'SELECT count(*) FROM "{tabela}"'
                ).fetchone()["count"]
    return totais


def violacoes_de_integridade(dsn: str | None = None) -> list[tuple[str, str, str, int]]:
    """Retorna [(tabela, coluna, tabela_referenciada, nº de órfãos)] por FK violada."""

    violacoes: list[tuple[str, str, str, int]] = []
    with conectar(dsn) as conexao:
        fks = conexao.execute(
            """
            SELECT conrelid::regclass::text            AS tabela,
                   confrelid::regclass::text           AS referencia,
                   con.conkey[1]                       AS col_local,
                   con.confkey[1]                      AS col_ref,
                   att_local.attname                   AS coluna,
                   att_ref.attname                     AS coluna_ref
            FROM pg_constraint con
            JOIN pg_attribute att_local
                 ON att_local.attrelid = con.conrelid AND att_local.attnum = con.conkey[1]
            JOIN pg_attribute att_ref
                 ON att_ref.attrelid = con.confrelid AND att_ref.attnum = con.confkey[1]
            JOIN pg_class cl ON cl.oid = con.conrelid
            JOIN pg_namespace ns ON ns.oid = cl.relnamespace
            WHERE con.contype = 'f' AND ns.nspname = 'public'
            """
        ).fetchall()
        for fk in fks:
            orfaos = conexao.execute(
                f"""
                SELECT count(*)
                FROM public.{fk['tabela']} t
                LEFT JOIN public.{fk['referencia']} r ON r.{fk['coluna_ref']} = t.{fk['coluna']}
                WHERE r.{fk['coluna_ref']} IS NULL
                """,
            ).fetchone()["count"]
            if orfaos:
                violacoes.append(
                    (fk["tabela"], fk["coluna"], fk["referencia"], orfaos)
                )
    return violacoes