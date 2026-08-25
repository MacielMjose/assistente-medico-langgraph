"""Migração SQLite -> PostgreSQL 17 + pgvector.

Uso:
    docker compose up -d
    python database/migrate_sqlite_to_pg.py                     # dim=384 (e5 local)
    python database/migrate_sqlite_to_pg.py --dim 1536          # openai
    MEDPT_PG_DSN=postgresql://... python database/migrate_sqlite_to_pg.py

Idempotente: recria o schema e recarrega tudo a cada execução.
"""

import argparse
import os
import sqlite3
import sys
import time
from datetime import date, datetime
from pathlib import Path

import numpy as np
import psycopg
from pgvector.psycopg import register_vector

RAIZ_PROJETO = Path(__file__).resolve().parents[1]
if str(RAIZ_PROJETO) not in sys.path:
    sys.path.insert(0, str(RAIZ_PROJETO))

from src.db.connection import DB_PADRAO

DSN_PADRAO = "postgresql://medico:medico_dev@localhost:5433/assistente_medico"
SCHEMA_PG = RAIZ_PROJETO / "database" / "schema_postgres.sql"
TAMANHO_LOTE = 5_000

ORDEM_DAS_TABELAS = [
    ("especialidades", ["id", "nome"]),
    ("condicoes", ["id", "nome"]),
    ("tipos_questao", ["id", "nome"]),
    ("profissionais", ["id", "nome", "registro_conselho", "especialidade_principal_id", "criado_em"]),
    ("profissional_especialidade", ["profissional_id", "especialidade_id"]),
    (
        "pacientes",
        ["id", "nome", "cpf_mascarado", "data_nascimento", "sexo", "telefone_mock", "criado_em"],
    ),
    ("paciente_condicao", ["paciente_id", "condicao_id", "data_diagnostico", "status"]),
    (
        "atendimentos",
        [
            "id",
            "dataset_ref",
            "paciente_id",
            "profissional_id",
            "condicao_id",
            "tipo_questao_id",
            "data_atendimento",
            "queixa",
            "conduta",
        ],
    ),
    ("exames", ["id", "atendimento_id", "nome_exame", "data_exame", "resultado"]),
    (
        "prontuario_chunks",
        ["id", "atendimento_id", "ordem_chunk", "conteudo", "embedding", "modelo_embedding", "dimensoes"],
    ),
    ("log_auditoria", ["id", "sessao_id", "acao", "detalhe", "criado_em"]),
]

TABELAS_COM_IDENTIDADE = [
    "especialidades",
    "condicoes",
    "tipos_questao",
    "profissionais",
    "pacientes",
    "atendimentos",
    "exames",
    "prontuario_chunks",
    "log_auditoria",
]

COLUNAS_DATA = {"data_nascimento", "data_diagnostico", "data_exame"}
COLUNAS_DATETIME = {"data_atendimento", "criado_em"}


def _preparar_valor(coluna: str, valor):
    if valor is None or isinstance(valor, (int, float)):
        return valor
    if isinstance(valor, bytes):
        return np.frombuffer(valor, dtype="<f4")
    if isinstance(valor, str):
        if coluna in COLUNAS_DATETIME:
            return datetime.fromisoformat(valor)
        if coluna in COLUNAS_DATA:
            return date.fromisoformat(valor)
    return valor


def _copiar_tabela(origem: sqlite3.Connection, destino, tabela: str, colunas: list[str]) -> int:
    lista_colunas = ", ".join(colunas)
    linhas = origem.execute(f"SELECT {lista_colunas} FROM {tabela}").fetchall()
    placeholders = ", ".join(["%s"] * len(colunas))
    instrucao = f"INSERT INTO {tabela} ({lista_colunas}) VALUES ({placeholders})"
    with destino.cursor() as cursor:
        for inicio in range(0, len(linhas), TAMANHO_LOTE):
            lote = [
                tuple(_preparar_valor(campo, linha[campo]) for campo in colunas)
                for linha in linhas[inicio : inicio + TAMANHO_LOTE]
            ]
            cursor.executemany(instrucao, lote)
    return len(linhas)


def migrar(caminho_sqlite: Path, dsn: str, dimensoes: int) -> dict[str, int]:
    if not caminho_sqlite.exists():
        raise FileNotFoundError(
            f"SQLite não encontrado em '{caminho_sqlite}'. Gere com: python database/etl_seed.py"
        )
    inicio = time.perf_counter()
    ddl = SCHEMA_PG.read_text(encoding="utf-8").replace("__DIM__", str(dimensoes))

    origem = sqlite3.connect(f"file:{caminho_sqlite}?mode=ro", uri=True)
    origem.row_factory = sqlite3.Row
    contagens: dict[str, int] = {}

    try:
        with psycopg.connect(dsn) as destino:
            print("[migra] criando schema pgvector...")
            destino.execute(
                """
                DROP VIEW IF EXISTS
                    vw_historico_paciente, vw_exames_paciente, vw_estatisticas_base;
                DROP TABLE IF EXISTS
                    log_auditoria, prontuario_chunks, exames, atendimentos,
                    paciente_condicao, pacientes, profissional_especialidade,
                    profissionais, tipos_questao, condicoes, especialidades
                CASCADE;
                """
            )
            destino.execute(ddl)
            register_vector(destino)
            nomes = [tabela for tabela, _ in ORDEM_DAS_TABELAS]
            destino.execute(f"TRUNCATE {', '.join(nomes)} RESTART IDENTITY CASCADE")

            for tabela, colunas in ORDEM_DAS_TABELAS:
                contagens[tabela] = _copiar_tabela(origem, destino, tabela, colunas)
                print(f"[migra]   {tabela:<28} {contagens[tabela]:>9,}".replace(",", "."))

            print("[migra] ANALYZE...")
            destino.execute("ANALYZE")
            for tabela in TABELAS_COM_IDENTIDADE:
                destino.execute(
                    f"""
                    SELECT setval(
                        pg_get_serial_sequence('{tabela}', 'id'),
                        COALESCE((SELECT MAX(id) FROM {tabela}), 0) + 1,
                        false
                    )
                    """
                )
            destino.commit()
    finally:
        origem.close()

    print(
        f"=== Migração concluída ===\n"
        f"tabelas: {len(contagens)} | linhas: {sum(contagens.values()):,} | "
        f"duração: {time.perf_counter() - inicio:.1f}s".replace(",", ".")
    )
    return contagens


def main() -> None:
    parser = argparse.ArgumentParser(description="Copia a base SQLite para Postgres+pgvector.")
    parser.add_argument("--sqlite", type=Path, default=DB_PADRAO)
    parser.add_argument("--dsn", default=os.getenv("MEDPT_PG_DSN", DSN_PADRAO))
    parser.add_argument("--dim", type=int, default=384, help="Dimensão do vetor (384 e5 / 1536 openai).")
    argumentos = parser.parse_args()
    migrar(argumentos.sqlite, argumentos.dsn, argumentos.dim)


if __name__ == "__main__":
    main()
