import json
import os

import psycopg
from psycopg.rows import dict_row
from pgvector.psycopg import register_vector

from src.db.models import (
    Atendimento,
    CondicaoPaciente,
    EntradaLog,
    EstatisticasBase,
    Exame,
    Paciente,
    ResultadoBusca,
    ResultadoVetorial,
)

DSN_PADRAO = "postgresql://medico:medico_dev@localhost:5433/assistente_medico"
LIMITE_PADRAO_PRONTUARIOS = 20
LIMITE_PADRAO_BUSCA = 10


class RepositorioClinicoPg:
    def __init__(self, dsn: str | None = None):
        self._dsn = dsn or os.getenv("MEDPT_PG_DSN", DSN_PADRAO)

    def _abrir(self):
        conexao = psycopg.connect(self._dsn, row_factory=dict_row)
        register_vector(conexao)
        return conexao

    @staticmethod
    def _para_paciente(linha: dict) -> Paciente:
        return Paciente(**linha)

    @staticmethod
    def _para_atendimento(linha: dict) -> Atendimento:
        dados = {chave: valor for chave, valor in linha.items() if chave != "busca"}
        return Atendimento(**dados)

    def buscar_paciente(self, nome: str, limite: int = 10) -> list[Paciente]:
        with self._abrir() as con:
            linhas = con.execute(
                """
                SELECT id, nome, cpf_mascarado, data_nascimento, sexo, telefone_mock, criado_em
                FROM pacientes
                WHERE nome ILIKE %(termo)s
                ORDER BY nome
                LIMIT %(limite)s
                """,
                {"termo": f"%{nome.strip()}%", "limite": limite},
            ).fetchall()
        return [self._para_paciente(linha) for linha in linhas]

    def obter_paciente(self, paciente_id: int) -> Paciente | None:
        with self._abrir() as con:
            linha = con.execute(
                """
                SELECT id, nome, cpf_mascarado, data_nascimento, sexo, telefone_mock, criado_em
                FROM pacientes WHERE id = %s
                """,
                (paciente_id,),
            ).fetchone()
        return self._para_paciente(linha) if linha else None

    def obter_prontuarios(
        self, paciente_id: int, limite: int = LIMITE_PADRAO_PRONTUARIOS
    ) -> list[Atendimento]:
        with self._abrir() as con:
            linhas = con.execute(
                """
                SELECT id, dataset_ref, paciente_id, profissional_id, condicao_id,
                       tipo_questao_id, data_atendimento, queixa, conduta, busca
                FROM atendimentos
                WHERE paciente_id = %s
                ORDER BY data_atendimento DESC, id DESC
                LIMIT %s
                """,
                (paciente_id, limite),
            ).fetchall()
        return [self._para_atendimento(linha) for linha in linhas]

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

    def estatisticas(self) -> EstatisticasBase:
        with self._abrir() as con:
            linha = con.execute("SELECT * FROM vw_estatisticas_base").fetchone()
        return EstatisticasBase(**linha)

    def buscar_texto(
        self,
        termo: str,
        condicao: str | None = None,
        limite: int = LIMITE_PADRAO_BUSCA,
    ) -> list[ResultadoBusca]:
        filtro = "AND c.nome = %(condicao)s" if condicao else ""
        sql = f"""
            SELECT
                a.id            AS atendimento_id,
                a.paciente_id,
                c.nome          AS condicao,
                e.nome          AS especialidade_principal,
                a.data_atendimento,
                a.queixa,
                a.conduta,
                ts_rank(a.busca, consulta) AS relevancia
            FROM atendimentos a
            JOIN condicoes c ON c.id = a.condicao_id
            JOIN profissionais pr ON pr.id = a.profissional_id
            JOIN especialidades e ON e.id = pr.especialidade_principal_id,
                 plainto_tsquery('portuguese', %(termo)s) AS consulta
            WHERE a.busca @@ consulta {filtro}
            ORDER BY relevancia DESC
            LIMIT %(limite)s
        """
        with self._abrir() as con:
            linhas = con.execute(
                sql, {"termo": termo, "condicao": condicao, "limite": limite}
            ).fetchall()
        return [ResultadoBusca(**linha) for linha in linhas]

    def buscar_vetorial(
        self,
        consulta: str,
        provedor,
        k: int = 5,
        condicao: str | None = None,
    ) -> list[ResultadoVetorial]:
        vetor = provedor.embed_consulta(consulta)
        filtro = "AND c.nome = %(condicao)s" if condicao else ""
        sql = f"""
            SELECT
                ch.atendimento_id,
                a.paciente_id,
                ch.ordem_chunk,
                ch.conteudo,
                a.data_atendimento,
                c.nome  AS condicao,
                e.nome  AS especialidade_principal,
                1 - (ch.embedding <=> %(vetor)s::vector) AS similaridade
            FROM prontuario_chunks ch
            JOIN atendimentos a ON a.id = ch.atendimento_id
            JOIN condicoes c ON c.id = a.condicao_id
            JOIN profissionais pr ON pr.id = a.profissional_id
            JOIN especialidades e ON e.id = pr.especialidade_principal_id
            WHERE ch.modelo_embedding = %(modelo)s {filtro}
            ORDER BY ch.embedding <=> %(vetor)s::vector
            LIMIT %(k)s
        """
        with self._abrir() as con:
            linhas = con.execute(
                sql,
                {
                    "vetor": vetor,
                    "modelo": provedor.nome_modelo,
                    "condicao": condicao,
                    "k": k,
                },
            ).fetchall()
        return [
            ResultadoVetorial(**{**linha, "similaridade": round(float(linha["similaridade"]), 4)})
            for linha in linhas
        ]
