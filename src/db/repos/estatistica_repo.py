"""Estatísticas gerais da base."""

from src.db.models import EstatisticasBase
from src.db.repos.base import RepositorioBase


class EstatisticaRepositorio(RepositorioBase):
    def estatisticas(self) -> EstatisticasBase:
        with self._abrir() as con:
            linha = con.execute("SELECT * FROM vw_estatisticas_base").fetchone()
        return EstatisticasBase(**linha)