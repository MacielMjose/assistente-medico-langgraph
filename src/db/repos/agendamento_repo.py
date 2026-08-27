"""Operações de agendamentos de consultas."""

from src.db.models import Agendamento
from src.db.repos.base import RepositorioBase

COLUNAS_AGENDAMENTO = (
    "id, paciente_id, profissional_id, especialidade_id, data_hora_agendada, "
    "data_hora_realizada, status, motivo, observacoes, duracao_minutos, "
    "lembrete_enviado, recorrente, criado_em, atualizado_em"
)


class AgendamentoRepositorio(RepositorioBase):
    def obter_agendamentos(self, paciente_id: int, limite: int = 50) -> list[Agendamento]:
        with self._abrir() as con:
            linhas = con.execute(
                f"""
                SELECT {COLUNAS_AGENDAMENTO}
                FROM agendamentos
                WHERE paciente_id = %s
                ORDER BY data_hora_agendada DESC
                LIMIT %s
                """,
                (paciente_id, limite),
            ).fetchall()
        return [Agendamento(**linha) for linha in linhas]

    def obter_agendamentos_por_periodo(
        self, data_inicio: str, data_fim: str, status: str | None = None
    ) -> list[Agendamento]:
        filtro = "AND status = %(status)s" if status else ""
        parametros: dict[str, object] = {"data_inicio": data_inicio, "data_fim": data_fim}
        if status:
            parametros["status"] = status
        sql = f"""
            SELECT {COLUNAS_AGENDAMENTO}
            FROM agendamentos
            WHERE data_hora_agendada BETWEEN %(data_inicio)s AND %(data_fim)s
            {filtro}
            ORDER BY data_hora_agendada
        """
        with self._abrir() as con:
            linhas = con.execute(sql, parametros).fetchall()
        return [Agendamento(**linha) for linha in linhas]

    def criar_agendamento(self, dados: dict) -> int:
        with self._abrir() as con:
            linha = con.execute(
                """
                INSERT INTO agendamentos
                    (paciente_id, profissional_id, especialidade_id, data_hora_agendada,
                     status, motivo, observacoes, duracao_minutos, lembrete_enviado, recorrente)
                VALUES
                    (%(paciente_id)s, %(profissional_id)s, %(especialidade_id)s, %(data_hora_agendada)s,
                     %(status)s, %(motivo)s, %(observacoes)s, %(duracao_minutos)s, %(lembrete_enviado)s, %(recorrente)s)
                RETURNING id
                """,
                dados,
            ).fetchone()
            con.commit()
        return linha["id"]

    def atualizar_status_agendamento(
        self, agendamento_id: int, status: str, data_hora_realizada: str | None = None
    ) -> bool:
        with self._abrir() as con:
            con.execute(
                """
                UPDATE agendamentos
                SET status = %s,
                    data_hora_realizada = %s,
                    atualizado_em = now()
                WHERE id = %s
                """,
                (status, data_hora_realizada, agendamento_id),
            )
            con.commit()
        return True