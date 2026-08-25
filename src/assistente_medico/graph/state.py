from sqlite3 import Date
from typing import TypedDict


class DadosPaciente(TypedDict):
    nome: str
    cpf: str | None
    ja_existe: bool
    exames: list[dict] | None
    data_ultima_consulta: Date | None
    prontuarios: list[dict] | None
    tratamento_necessario: bool
    mensagem_final: str
