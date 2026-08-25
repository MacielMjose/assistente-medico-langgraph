from langchain_core.prompts import PromptTemplate
from src.assistente_medico.llm.config import get_llm
from src.assistente_medico.graph.state import DadosPaciente


llm = get_llm()

prompt = PromptTemplate.from_template(
    "Com base no nome {nome}, escolha o clima da personalidade da pessoa hoje. "
    "Responda apenas com uma das três palavras: Ensolarado, Nublado ou Chuvoso."
)


def obter_entrada(state: DadosPaciente) -> DadosPaciente:
    return state


def validar_dados_paciente(state: DadosPaciente) -> DadosPaciente:
    return state


def buscar_paciente(state: DadosPaciente) -> DadosPaciente:
    return state


def obter_prontuarios(state: DadosPaciente) -> DadosPaciente:
    return state


def buscar_exames(state: DadosPaciente) -> DadosPaciente:
    return state


def consultar_modelo_llm(state: DadosPaciente) -> DadosPaciente:
    return state


def gerar_explicacao(state: DadosPaciente) -> DadosPaciente:
    return state


def validar_com_profissional(state: DadosPaciente) -> DadosPaciente:
    return state


def sugerir_tratamentos(state: DadosPaciente) -> DadosPaciente:
    return state


def emitir_alertas(state: DadosPaciente) -> DadosPaciente:
    return state


def registrar_log_auditoria(state: DadosPaciente) -> DadosPaciente:
    return state


def marcar_consulta(state: DadosPaciente) -> DadosPaciente:
    return state
