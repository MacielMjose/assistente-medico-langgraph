from src.db.connection import (
    aplicar_schema,
    conectar,
    contagem_por_tabela,
    recriar_schema,
    resolver_dsn,
    sessao,
    violacoes_de_integridade,
)
from src.db.models import (
    Agendamento,
    Atendimento,
    CondicaoPaciente,
    EntradaLog,
    EstatisticasBase,
    Exame,
    Paciente,
    ResultadoBusca,
    ResultadoConhecimento,
)
from src.db.buscar import BuscaRepositorio
from src.db.embeddings import (
    dividir_em_chunks,
    nome_modelo_do,
    obter_provedor,
)
from src.db.repos import (
    AgendamentoRepositorio,
    AtendimentoRepositorio,
    EstatisticaRepositorio,
    LogRepositorio,
    PacienteRepositorio,
)
from src.db.vectorstore import (
    apagar_colecao,
    estatisticas_chunks,
    obter_vectorstore,
    obter_vectorstore_conhecimento,
    colecao_conhecimento_para,
)

__all__ = [
    "conectar",
    "sessao",
    "resolver_dsn",
    "aplicar_schema",
    "recriar_schema",
    "contagem_por_tabela",
    "violacoes_de_integridade",
    "BuscaRepositorio",
    "obter_provedor",
    "dividir_em_chunks",
    "nome_modelo_do",
    "obter_vectorstore",
    "obter_vectorstore_conhecimento",
    "colecao_conhecimento_para",
    "apagar_colecao",
    "estatisticas_chunks",
    "AgendamentoRepositorio",
    "AtendimentoRepositorio",
    "EstatisticaRepositorio",
    "LogRepositorio",
    "PacienteRepositorio",
    "Paciente",
    "Atendimento",
    "CondicaoPaciente",
    "Exame",
    "Agendamento",
    "ResultadoBusca",
    "ResultadoConhecimento",
    "EntradaLog",
    "EstatisticasBase",
]