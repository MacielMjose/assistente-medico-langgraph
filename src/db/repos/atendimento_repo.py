"""Histórico clínico: atendimentos, condições e exames do paciente."""

from src.db.models import Atendimento, CondicaoPaciente, Exame
from src.db.repos.base import RepositorioBase

LIMITE_PADRAO_PRONTUARIOS = 20


class AtendimentoRepositorio(RepositorioBase):
    def obter_prontuarios(
        self, paciente_id: int, limite: int = LIMITE_PADRAO_PRONTUARIOS
    ) -> list[Atendimento]:
        with self._abrir() as con:
            linhas = con.execute(
                """
                SELECT id, dataset_ref, paciente_id, profissional_id, condicao_id,
                       tipo_questao_id, data_atendimento, queixa, conduta
                FROM atendimentos
                WHERE paciente_id = %s
                ORDER BY data_atendimento DESC, id DESC
                LIMIT %s
                """,
                (paciente_id, limite),
            ).fetchall()
        return [Atendimento(**linha) for linha in linhas]

    def obter_condicoes(self, paciente_id: int) -> list[CondicaoPaciente]:
        with self._abrir() as con:
            linhas = con.execute(
                """
                SELECT c.nome AS condicao, pc.status, pc.data_diagnostico
                FROM paciente_condicao pc
                JOIN condicoes c ON c.id = pc.condicao_id
                WHERE pc.paciente_id = %s
                ORDER BY pc.data_diagnostico
                """,
                (paciente_id,),
            ).fetchall()
        return [CondicaoPaciente(**linha) for linha in linhas]

    def obter_exames(self, paciente_id: int, limite: int = 50) -> list[Exame]:
        with self._abrir() as con:
            linhas = con.execute(
                """
                SELECT exame_id, atendimento_id, paciente_id, nome_exame, data_exame, resultado
                FROM vw_exames_paciente
                WHERE paciente_id = %s
                ORDER BY data_exame DESC, exame_id DESC
                LIMIT %s
                """,
                (paciente_id, limite),
            ).fetchall()
        return [Exame(**linha) for linha in linhas]