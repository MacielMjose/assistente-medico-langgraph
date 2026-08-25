"""Gera os schemas monolíticos (schema.sql / schema_postgres.sql) a partir dos scripts individuais.

Uso:
    python database/rebuild_schema.py

Lê todos os arquivos *.sql de database/scripts/sqlite/ e database/scripts/postgres/
em ordem alfabética (garantida pelo prefixo numérico) e concatena nos arquivos
schema.sql e schema_postgres.sql, respectivamente.
"""

from pathlib import Path

RAIZ_PROJETO = Path(__file__).resolve().parents[1]
SCRIPTS_SQLITE = RAIZ_PROJETO / "database" / "scripts" / "sqlite"
SCRIPTS_POSTGRES = RAIZ_PROJETO / "database" / "scripts" / "postgres"

HEADER_SQLITE = """\
-- ============================================================================
-- Schema simulado de prontuários médicos (SQLite)
-- Projeto: assistente-medico-langgraph
-- *** ARQUIVO AUTO-GERADO *** Execute: python database/rebuild_schema.py
--
-- Convenções:
--   * ids INTEGER PRIMARY KEY (rowid alias, sem autoincrement explícito)
--   * datas em ISO-8601; DATE/DATETIME convertidos via detect_types
--   * FTS5 externo a atendimentos: populado pelo ETL (carga read-only)
--   * prontuario_chunks.embedding BLOB = float32 little-endian empacotado;
--     na migração p/ Postgres+pgvector vira vector(dim) + índice HNSW
-- ============================================================================

"""

HEADER_POSTGRES = """\
-- ============================================================================
-- Schema de prontuários médicos (PostgreSQL 17 + pgvector)
-- *** ARQUIVO AUTO-GERADO *** Execute: python database/rebuild_schema.py
--
-- O placeholder __DIM__ é substituído pelo migrador conforme o modelo de
-- embeddings usado (384 p/ e5-local, 1536 p/ text-embedding-3-small).
-- Executável também via psql:  sed 's/__DIM__/384/' schema_postgres.sql | psql ...
-- ============================================================================

"""


def _concatenar_scripts(diretorio: Path, header: str) -> str:
    partes = [header]
    for arquivo in sorted(diretorio.glob("*.sql")):
        partes.append(arquivo.read_text(encoding="utf-8"))
        partes.append("\n")
    return "\n".join(partes)


def rebuild() -> None:
    destino_sqlite = RAIZ_PROJETO / "database" / "schema.sql"
    destino_pg = RAIZ_PROJETO / "database" / "schema_postgres.sql"

    destino_sqlite.write_text(
        _concatenar_scripts(SCRIPTS_SQLITE, HEADER_SQLITE), encoding="utf-8"
    )
    print(f"[rebuild] {destino_sqlite}")

    destino_pg.write_text(
        _concatenar_scripts(SCRIPTS_POSTGRES, HEADER_POSTGRES), encoding="utf-8"
    )
    print(f"[rebuild] {destino_pg}")


if __name__ == "__main__":
    rebuild()
