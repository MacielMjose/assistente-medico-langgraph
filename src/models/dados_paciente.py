
from sqlite3 import Date
from typing import TypedDict, Any, Optional

class DadosPaciente(TypedDict, total=False):
    nome: str
    cpf: Optional[str]
    ja_existe: bool
    paciente: Optional[Any]
    exames: Optional[list[dict]]
    data_ultima_consulta: Optional[Date]
    prontuarios: Optional[list[dict]]
    tratamento_necessario: bool
    mensagem_final: str
    analise_llm: str
    alergias_extraidas: Optional[list[dict]]
    explicacao: str
    validacao_profissional: dict
    tratamentos: str
    validacao_alergias: Optional[dict]
    agendamento: Optional[dict]
    alertas: list[str]
    log_id: Optional[Any]
    documentos_similares: Optional[list[dict]]