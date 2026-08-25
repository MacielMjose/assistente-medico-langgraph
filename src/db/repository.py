import json

from src.db.connection import sessao
from src.db.models import (
    Agendamento,
    Atendimento,
    CondicaoPaciente,
    EntradaLog,
    EstatisticasBase,
    Exame,
    Paciente,
    ResultadoBusca,
)

LIMITE_PADRAO_PRONTUARIOS = 20
LIMITE_PADRAO_BUSCA = 10


class RepositorioClinico:
    def __init__(self, caminho_db=None):
        self._caminho_db = caminho_db

    def _abrir(self):
        return sessao(self._caminho_db)

    @staticmethod
    def _para_paciente(linha) -> Paciente:
        return Paciente(**dict(linha))

    @staticmethod
    def _para_atendimento(linha) -> Atendimento:
        return Atendimento(**dict(linha))

    def buscar_paciente(self, nome: str, limite: int = 10) -> list[Paciente]:
        termo = f"%{nome.strip()}%"
        with self._abrir() as con:
            linhas = con.execute(
                """
                SELECT id, nome, cpf_mascarado, data_nascimento, sexo, telefone_mock, criado_em
                FROM pacientes
                WHERE nome LIKE :termo COLLATE NOCASE
                ORDER BY nome
                LIMIT :limite
                """,
                {"termo": termo, "limite": limite},
            ).fetchall()
        return [self._para_paciente(linha) for linha in linhas]

    def obter_paciente(self, paciente_id: int) -> Paciente | None:
        with self._abrir() as con:
            linha = con.execute(
                """
                SELECT id, nome, cpf_mascarado, data_nascimento, sexo, telefone_mock, criado_em
                FROM pacientes
                WHERE id = :id
                """,
                {"id": paciente_id},
            ).fetchone()
        return self._para_paciente(linha) if linha else None

    def obter_prontuarios(self, paciente_id: int, limite: int = LIMITE_PADRAO_PRONTUARIOS) -> list[Atendimento]:
        with self._abrir() as con:
            linhas = con.execute(
                """
                SELECT *
                FROM atendimentos
                WHERE paciente_id = :paciente_id
                ORDER BY data_atendimento DESC, id DESC
                LIMIT :limite
                """,
                {"paciente_id": paciente_id, "limite": limite},
            ).fetchall()
        return [self._para_atendimento(linha) for linha in linhas]

    def obter_condicoes(self, paciente_id: int) -> list[CondicaoPaciente]:
        with self._abrir() as con:
            linhas = con.execute(
                """
                SELECT c.nome AS condicao, pc.status, pc.data_diagnostico
                FROM paciente_condicao pc
                JOIN condicoes c ON c.id = pc.condicao_id
                WHERE pc.paciente_id = :paciente_id
                ORDER BY pc.data_diagnostico
                """,
                {"paciente_id": paciente_id},
            ).fetchall()
        return [CondicaoPaciente(**dict(linha)) for linha in linhas]

    def obter_exames(self, paciente_id: int, limite: int = 50) -> list[Exame]:
        with self._abrir() as con:
            linhas = con.execute(
                """
                SELECT exame_id, atendimento_id, paciente_id, nome_exame, data_exame, resultado
                FROM vw_exames_paciente
                WHERE paciente_id = :paciente_id
                ORDER BY data_exame DESC, exame_id DESC
                LIMIT :limite
                """,
                {"paciente_id": paciente_id, "limite": limite},
            ).fetchall()
        return [Exame(**dict(linha)) for linha in linhas]

    def buscar_texto(
        self,
        termo: str,
        condicao: str | None = None,
        limite: int = LIMITE_PADRAO_BUSCA,
    ) -> list[ResultadoBusca]:
        consulta = f'"{termo.strip().replace(chr(34), chr(34) * 2)}"'
        filtros = "AND c.nome = :condicao" if condicao else ""
        sql = f"""
            SELECT
                a.id            AS atendimento_id,
                a.paciente_id,
                c.nome          AS condicao,
                e.nome          AS especialidade_principal,
                a.data_atendimento,
                a.queixa,
                a.conduta,
                bm25(atendimentos_fts) AS relevancia
            FROM atendimentos_fts f
            JOIN atendimentos a ON a.id = f.rowid
            JOIN condicoes c ON c.id = a.condicao_id
            JOIN profissionais pr ON pr.id = a.profissional_id
            JOIN especialidades e ON e.id = pr.especialidade_principal_id
            WHERE atendimentos_fts MATCH :consulta {filtros}
            ORDER BY relevancia
            LIMIT :limite
        """
        parametros = {"consulta": consulta, "condicao": condicao, "limite": limite}
        with self._abrir() as con:
            linhas = con.execute(sql, parametros).fetchall()
        return [ResultadoBusca(**dict(linha)) for linha in linhas]

    def registrar_log(self, entrada: EntradaLog) -> int:
        detalhe = json.dumps(entrada.detalhe, ensure_ascii=False)
        with self._abrir() as con:
            cursor = con.execute(
                """
                INSERT INTO log_auditoria (sessao_id, acao, detalhe)
                VALUES (:sessao_id, :acao, :detalhe)
                """,
                {"sessao_id": entrada.sessao_id, "acao": entrada.acao, "detalhe": detalhe},
            )
            con.commit()
            return cursor.lastrowid

    def estatisticas(self) -> EstatisticasBase:
        with self._abrir() as con:
            linha = con.execute("SELECT * FROM vw_estatisticas_base").fetchone()
        return EstatisticasBase(**dict(linha))

    def obter_agendamentos(
        self, paciente_id: int, limite: int = 50
    ) -> list[Agendamento]:
        with self._abrir() as con:
            linhas = con.execute(
                """
                SELECT id, paciente_id, profissional_id, especialidade_id,
                       data_hora_agendada, data_hora_realizada, status, motivo,
                       observacoes, duracao_minutos, lembrete_enviado, recorrente,
                       criado_em, atualizado_em
                FROM agendamentos
                WHERE paciente_id = :paciente_id
                ORDER BY data_hora_agendada DESC
                LIMIT :limite
                """,
                {"paciente_id": paciente_id, "limite": limite},
            ).fetchall()
        return [Agendamento(**dict(linha)) for linha in linhas]

    def obter_agendamentos_por_periodo(
        self, data_inicio: str, data_fim: str, status: str | None = None
    ) -> list[Agendamento]:
        filtros = ""
        parametros: dict = {"data_inicio": data_inicio, "data_fim": data_fim}
        if status:
            filtros = "AND status = :status"
            parametros["status"] = status
        sql = f"""
            SELECT id, paciente_id, profissional_id, especialidade_id,
                   data_hora_agendada, data_hora_realizada, status, motivo,
                   observacoes, duracao_minutos, lembrete_enviado, recorrente,
                   criado_em, atualizado_em
            FROM agendamentos
            WHERE data_hora_agendada BETWEEN :data_inicio AND :data_fim
            {filtros}
            ORDER BY data_hora_agendada
        """
        with self._abrir() as con:
            linhas = con.execute(sql, parametros).fetchall()
        return [Agendamento(**dict(linha)) for linha in linhas]

    def criar_agendamento(self, dados: dict) -> int:
        with self._abrir() as con:
            cursor = con.execute(
                """
                INSERT INTO agendamentos
                    (paciente_id, profissional_id, especialidade_id, data_hora_agendada,
                     status, motivo, observacoes, duracao_minutos, lembrete_enviado, recorrente)
                VALUES
                    (:paciente_id, :profissional_id, :especialidade_id, :data_hora_agendada,
                     :status, :motivo, :observacoes, :duracao_minutos, :lembrete_enviado, :recorrente)
                """,
                dados,
            )
            con.commit()
            return cursor.lastrowid

    def atualizar_status_agendamento(
        self, agendamento_id: int, status: str, data_hora_realizada: str | None = None
    ) -> bool:
        with self._abrir() as con:
            con.execute(
                """
                UPDATE agendamentos
                SET status = :status,
                    data_hora_realizada = :data_hora_realizada,
                    atualizado_em = CURRENT_TIMESTAMP
                WHERE id = :id
                """,
                {"id": agendamento_id, "status": status, "data_hora_realizada": data_hora_realizada},
            )
            con.commit()
            return con.total_changes > 0
