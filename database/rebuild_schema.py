"""Gera o schema monolítico schema_postgres.sql a partir dos scripts individuais.

Uso:
    python database/rebuild_schema.py

Lê todos os arquivos *.sql de database/scripts/postgres/ em ordem alfabética
(garantida pelo prefixo numérico) e concatena em schema_postgres.sql.
"""

from pathlib import Path

RAIZ_PROJETO = Path(__file__).resolve().parents[1]
SCRIPTS_POSTGRES = RAIZ_PROJETO / "database" / "scripts" / "postgres"

HEADER_POSTGRES = """\
-- ============================================================================
-- Schema de prontuários médicos (PostgreSQL 17 + pgvector)
-- *** ARQUIVO AUTO-GERADO *** Execute: python database/rebuild_schema.py
--
-- A busca vetorial é gerenciada pelo vector store do LangChain (PGVector):
-- as tabelas langchain_pg_collection e langchain_pg_embedding são criadas
-- automaticamente na primeira ingestão de embeddings (database/embeddings_ingest.py).
-- ============================================================================

"""


def _concatenar_scripts(diretorio: Path, header: str) -> str:
    partes = [header]
    for arquivo in sorted(diretorio.glob("*.sql")):
        partes.append(arquivo.read_text(encoding="utf-8"))
        partes.append("\n")
    return "\n".join(partes)


def rebuild() -> None:
    destino_pg = RAIZ_PROJETO / "database" / "schema_postgres.sql"
    destino_pg.write_text(
        _concatenar_scripts(SCRIPTS_POSTGRES, HEADER_POSTGRES), encoding="utf-8"
    )
    print(f"[rebuild] {destino_pg}")


if __name__ == "__main__":
    rebuild()