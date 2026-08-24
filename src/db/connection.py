import os
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path

RAIZ_PROJETO = Path(__file__).resolve().parents[2]
CAMINHO_SCHEMA = RAIZ_PROJETO / "database" / "schema.sql"
DB_PADRAO = RAIZ_PROJETO / "database" / "assistente_medico.db"


def _registrar_adaptadores() -> None:
    sqlite3.register_adapter(date, lambda valor: valor.isoformat())
    sqlite3.register_adapter(datetime, lambda valor: valor.isoformat(sep=" ", timespec="seconds"))
    sqlite3.register_converter("DATE", lambda bruto: date.fromisoformat(bruto.decode()))
    sqlite3.register_converter("DATETIME", lambda bruto: datetime.fromisoformat(bruto.decode()))


_registrar_adaptadores()


def resolver_caminho_db(caminho: str | Path | None = None) -> Path:
    escolhido = caminho or os.getenv("MEDPT_DB_PATH") or DB_PADRAO
    return Path(escolhido)


def conectar(caminho: str | Path | None = None) -> sqlite3.Connection:
    destino = resolver_caminho_db(caminho)
    if not destino.exists():
        raise FileNotFoundError(
            f"Base não encontrada em '{destino}'. Gere-a com: python database/etl_seed.py"
        )
    conexao = sqlite3.connect(destino, detect_types=sqlite3.PARSE_DECLTYPES)
    conexao.row_factory = sqlite3.Row
    conexao.execute("PRAGMA foreign_keys = ON")
    return conexao


@contextmanager
def sessao(caminho: str | Path | None = None):
    conexao = conectar(caminho)
    try:
        yield conexao
    finally:
        conexao.close()


def aplicar_schema(conexao: sqlite3.Connection, caminho_schema: str | Path | None = None) -> None:
    destino = Path(caminho_schema) if caminho_schema else CAMINHO_SCHEMA
    conexao.executescript(destino.read_text(encoding="utf-8"))
    conexao.commit()
