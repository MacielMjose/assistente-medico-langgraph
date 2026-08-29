"""Operações de pacientes."""

from src.db.models import Paciente
from src.db.repos.base import RepositorioBase

COLUNAS_PACIENTE = (
    "id, nome, cpf_mascarado, data_nascimento, sexo, telefone_mock, criado_em"
)


class PacienteRepositorio(RepositorioBase):
    def buscar_paciente(self, nome: str, limite: int = 10) -> list[Paciente]:
        with self._abrir() as con:
            linhas = con.execute(
                f"""
                SELECT {COLUNAS_PACIENTE}
                FROM pacientes
                WHERE nome ILIKE '%%' || %(termo)s || '%%'
                ORDER BY nome
                LIMIT %(limite)s
                """,
                {"termo": nome.strip(), "limite": limite},
            ).fetchall()
        return [Paciente(**linha) for linha in linhas]

    def obter_paciente(self, paciente_id: int) -> Paciente | None:
        with self._abrir() as con:
            linha = con.execute(
                f"""
                SELECT {COLUNAS_PACIENTE}
                FROM pacientes WHERE id = %s
                """,
                (paciente_id,),
            ).fetchone()
        return Paciente(**linha) if linha else None