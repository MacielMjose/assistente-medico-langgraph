import os
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from src.models.dados_paciente import DadosPaciente
from src.services.llm_provider_service import get_llm

llm = get_llm()

prompt = PromptTemplate.from_template(
    "Com base no nome {nome}, escolha o clima da personalidade da pessoa hoje. "
    "Responda apenas com uma das três palavras: Ensolarado, Nublado ou Chuvoso."
)


def obter_entrada(state: dict) -> dict:
    return state


def validar_dados_paciente(state: dict) -> dict:
    return state


def buscar_paciente(state: dict) -> dict:
    return state


def obter_prontuarios(state: dict) -> dict:
    return state


def buscar_exames(state: dict) -> dict:
    return state


def consultar_modelo_llm(state: dict) -> dict:
    return state


def gerar_explicacao(state: dict) -> dict:
    return state


def validar_com_profissional(state: dict) -> dict:
    return state


def sugerir_tratamentos(state: dict) -> dict:
    return state


def emitir_alertas(state: dict) -> dict:
    return state


def registrar_log_auditoria(state: dict) -> dict:
    return state


def marcar_consulta(state: dict) -> dict:
    return state


def verificar_paciente_existe(state: dict) -> str:
    return "paciente_existe" if state.get("paciente") else "paciente_nao_existe"


def verificar_tratamento_necessario(state: dict) -> str:
    return (
        "tratamento_necessario"
        if state.get("tratamento")
        else "tratamento_nao_necessario"
    )


workflow = StateGraph(DadosPaciente)

# Definição dos nós do grafo
workflow.add_node("obter_entrada", obter_entrada)
workflow.add_node("validar_dados_paciente", validar_dados_paciente)
workflow.add_node("buscar_paciente", buscar_paciente)
workflow.add_node("obter_prontuarios", obter_prontuarios)
workflow.add_node("consultar_modelo_llm", consultar_modelo_llm)
workflow.add_node("gerar_explicacao", gerar_explicacao)
workflow.add_node("validar_com_profissional", validar_com_profissional)
workflow.add_node("sugerir_tratamentos", sugerir_tratamentos)
workflow.add_node("marcar_consulta", marcar_consulta)
workflow.add_node("emitir_alertas", emitir_alertas)
workflow.add_node("registrar_log_auditoria", registrar_log_auditoria)

# Definição das arestas do grafo
workflow.add_edge("obter_entrada", "validar_dados_paciente")
workflow.add_edge("validar_dados_paciente", "buscar_paciente")
workflow.add_conditional_edges(
    "buscar_paciente",
    verificar_paciente_existe,
    {"paciente_existe": "obter_prontuarios", "paciente_nao_existe": "marcar_consulta"},
)
workflow.add_edge("obter_prontuarios", "consultar_modelo_llm")
workflow.add_edge("consultar_modelo_llm", "gerar_explicacao")
workflow.add_edge("gerar_explicacao", "validar_com_profissional")
workflow.add_edge("validar_com_profissional", "sugerir_tratamentos")
workflow.add_conditional_edges(
    "sugerir_tratamentos",
    verificar_tratamento_necessario,
    {
        "tratamento_necessario": "marcar_consulta",
        "tratamento_nao_necessario": "emitir_alertas",
    },
)
workflow.add_edge("emitir_alertas", "registrar_log_auditoria")

workflow.set_entry_point("obter_entrada")
workflow.set_finish_point("registrar_log_auditoria")
app = workflow.compile()

print("Estrutura do grafo:")
print(app.get_graph().draw_ascii())

entrada = {"nome": "José"}
resultado = app.invoke(entrada)

print("Mensagem:", resultado.get("mensagem_final", "<sem retorno>"))
