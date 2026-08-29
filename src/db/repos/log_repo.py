"""Registro de log de auditoria."""

import json

from src.db.models import EntradaLog
from src.db.repos.base import RepositorioBase


class LogRepositorio(RepositorioBase):
    def registrar_log(self, entrada: EntradaLog) -> int:
        detalhe = json.dumps(entrada.detalhe, ensure_ascii=False)
        with self._abrir() as con:
            linha = con.execute(
                """
                INSERT INTO log_auditoria (sessao_id, acao, detalhe)
                VALUES (%s, %s, %s::jsonb)
                RETURNING id
                """,
                (entrada.sessao_id, entrada.acao, detalhe),
            ).fetchone()
            con.commit()
        return linha["id"]