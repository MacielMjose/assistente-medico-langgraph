from datetime import date, datetime

from pydantic import BaseModel, Field


class Paciente(BaseModel):
    id: int
    nome: str
    cpf_mascarado: str
    data_nascimento: date
    sexo: str
    telefone_mock: str
    criado_em: datetime | None = None


class Atendimento(BaseModel):
    id: int
    dataset_ref: int
    paciente_id: int
    profissional_id: int
    condicao_id: int
    tipo_questao_id: int
    data_atendimento: datetime
    queixa: str
    conduta: str


class CondicaoPaciente(BaseModel):
    condicao: str
    status: str
    data_diagnostico: date


class Exame(BaseModel):
    exame_id: int
    atendimento_id: int
    paciente_id: int
    nome_exame: str
    data_exame: date
    resultado: str


class Agendamento(BaseModel):
    id: int
    paciente_id: int
    profissional_id: int
    especialidade_id: int
    data_hora_agendada: datetime
    data_hora_realizada: datetime | None = None
    status: str
    motivo: str | None = None
    observacoes: str | None = None
    duracao_minutos: int = 30
    lembrete_enviado: bool = False
    recorrente: bool = False
    criado_em: datetime | None = None
    atualizado_em: datetime | None = None


class ResultadoBusca(BaseModel):
    atendimento_id: int
    paciente_id: int
    condicao: str
    especialidade_principal: str
    data_atendimento: datetime
    queixa: str
    conduta: str
    relevancia: float


class ResultadoVetorial(BaseModel):
    atendimento_id: int
    paciente_id: int
    ordem_chunk: int
    similaridade: float
    conteudo: str
    condicao: str
    especialidade_principal: str
    data_atendimento: datetime


class EntradaLog(BaseModel):
    sessao_id: str
    acao: str
    detalhe: dict = Field(default_factory=dict)


class EstatisticasBase(BaseModel):
    pacientes: int
    profissionais: int
    atendimentos: int
    condicoes: int
    especialidades: int
    exames: int
    logs_auditoria: int
    agendamentos: int
