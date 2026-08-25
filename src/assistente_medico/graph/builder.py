from langgraph.graph import StateGraph, END
from src.assistente_medico.graph.state import DadosPaciente
from src.assistente_medico.graph.nodes import (
    obter_entrada,
    validar_dados_paciente,
    buscar_paciente,
    obter_prontuarios,
    consultar_modelo_llm,
    gerar_explicacao,
    validar_com_profissional,
    sugerir_tratamentos,
    emitir_alertas,
    registrar_log_auditoria,
    marcar_consulta,
)
from src.assistente_medico.graph.edges import (
    verificar_paciente_existe,
    verificar_tratamento_necessario,
)


def build_graph():
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

    return workflow.compile()
