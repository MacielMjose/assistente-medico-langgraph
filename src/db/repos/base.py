"""Base para os repositórios por entidade.

Cada repositório concentra somente as consultas da sua entidade, em oposição
à antiga god class `RepositorioClinico`.
"""

from contextlib import contextmanager

from src.db.connection import resolver_dsn, sessao


class RepositorioBase:
    def __init__(self, dsn: str | None = None):
        self._dsn = resolver_dsn(dsn)

    @contextmanager
    def _abrir(self):
        with sessao(self._dsn) as conexao:
            yield conexao