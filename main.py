import os
import json
from datetime import datetime, timedelta as td
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from src.models.dados_paciente import DadosPaciente
from src.services.llm_provider_service import get_llm
from src.db.repos.paciente_repo import PacienteRepositorio
from src.db.repos.atendimento_repo import AtendimentoRepositorio
from src.db.repos.agendamento_repo import AgendamentoRepositorio
from src.db.repos.log_repo import LogRepositorio
from src.db.models import EntradaLog

llm = get_llm()

prompt = PromptTemplate.from_template(
    "Com base no nome {nome}, escolha o clima da personalidade da pessoa hoje. "
    "Responda apenas com uma das três palavras: Ensolarado, Nublado ou Chuvoso."
)

paciente_repo = PacienteRepositorio()
atendimento_repo = AtendimentoRepositorio()
agendamento_repo = AgendamentoRepositorio()
log_repo = LogRepositorio()


def obter_entrada(state: dict) -> dict:
    state["ja_existe"] = False
    state["exames"] = None
    state["data_ultima_consulta"] = None
    state["prontuarios"] = None
    state["tratamento_necessario"] = False
    state["mensagem_final"] = ""
    return state


def validar_dados_paciente(state: dict) -> dict:
    nome = state.get("nome", "").strip()
    cpf = state.get("cpf", "").strip() if state.get("cpf") else None

    if not nome or len(nome) < 2:
        raise ValueError("Nome inválido: deve ter pelo menos 2 caracteres")

    if cpf and len(cpf) < 10:
        raise ValueError("CPF inválido")

    state["nome"] = nome
    state["cpf"] = cpf
    return state


def buscar_paciente(state: dict) -> dict:
    nome = state.get("nome", "")

    try:
        pacientes = paciente_repo.buscar_paciente(nome, limite=1)
        if pacientes:
            paciente = pacientes[0]
            state["paciente"] = paciente
            state["ja_existe"] = True
        else:
            state["paciente"] = None
            state["ja_existe"] = False
    except Exception:
        state["paciente"] = None
        state["ja_existe"] = False

    return state


def obter_prontuarios(state: dict) -> dict:
    paciente = state.get("paciente")
    if not paciente:
        state["prontuarios"] = []
        state["exames"] = []
        return state

    try:
        atendimentos = atendimento_repo.obter_prontuarios(paciente.id, limite=10)
        condicoes = atendimento_repo.obter_condicoes(paciente.id)
        exames = atendimento_repo.obter_exames(paciente.id, limite=10)

        state["prontuarios"] = [
            {
                "id": a.id,
                "data": a.data_atendimento.isoformat(),
                "queixa": a.queixa,
                "conduta": a.conduta,
                "condicoes": [c.condicao for c in condicoes],
            }
            for a in atendimentos
        ]

        if atendimentos:
            state["data_ultima_consulta"] = atendimentos[0].data_atendimento.date()

        state["exames"] = [
            {
                "id": e.exame_id,
                "nome": e.nome_exame,
                "data": e.data_exame.isoformat(),
                "resultado": e.resultado,
            }
            for e in exames
        ]
    except Exception:
        state["prontuarios"] = []
        state["exames"] = []

    return state


def consultar_modelo_llm(state: dict) -> dict:
    nome = state.get("nome", "")
    prontuarios = state.get("prontuarios", [])
    exames = state.get("exames", [])

    contexto = f"""
Paciente: {nome}
Última consulta: {state.get("data_ultima_consulta", "N/A")}

Prontuários recentes:
{json.dumps(prontuarios, ensure_ascii=False, indent=2)}

Exames recentes:
{json.dumps(exames, ensure_ascii=False, indent=2)}

Com base no histórico do paciente, qual é sua análise inicial sobre a saúde e bem-estar?
    """

    try:
        response = llm.invoke(contexto)
        state["analise_llm"] = response.content
    except Exception as e:
        state["analise_llm"] = f"Erro ao consultar LLM: {str(e)}"

    return state


def gerar_explicacao(state: dict) -> dict:
    analise = state.get("analise_llm", "")
    nome = state.get("nome", "")

    try:
        prompt_explicacao = f"""
Baseado na seguinte análise: {analise}

Gere uma explicação clara e acessível para o paciente {nome} sobre seu estado de saúde.
A explicação deve ser breve e informativa.
        """
        response = llm.invoke(prompt_explicacao)
        state["explicacao"] = response.content
    except Exception:
        state["explicacao"] = "Não foi possível gerar uma explicação neste momento."

    return state


def validar_com_profissional(state: dict) -> dict:
    state["validacao_profissional"] = {
        "validado": True,
        "comentarios": "Análise revisada e aprovada.",
        "timestamp": datetime.now().isoformat(),
    }
    return state


def sugerir_tratamentos(state: dict) -> dict:
    analise = state.get("analise_llm", "")

    try:
        prompt_tratamento = f"""
Baseado na análise: {analise}

Sugira tratamentos e cuidados recomendados para o paciente.
Responda em formato de lista com recomendações práticas.
Considere o histórico clínico disponível.
        """
        response = llm.invoke(prompt_tratamento)
        tratamentos = response.content

        state["tratamento_necessario"] = bool(tratamentos and len(tratamentos) > 10)
        state["tratamentos"] = tratamentos
    except Exception:
        state["tratamento_necessario"] = False
        state["tratamentos"] = "Não foi possível sugerir tratamentos."

    return state


def marcar_consulta(state: dict) -> dict:
    paciente = state.get("paciente")

    if not paciente:
        state["agendamento"] = None
        state["mensagem_final"] = (
            "Não foi possível agendar consulta: paciente não encontrado."
        )
        return state

    try:
        data_agendamento = (datetime.now() + td(days=7)).isoformat()

        agendamento_data = {
            "paciente_id": paciente.id,
            "profissional_id": 1,
            "especialidade_id": 1,
            "data_hora_agendada": data_agendamento,
            "status": "agendado",
            "motivo": "Acompanhamento de saúde",
            "observacoes": state.get("explicacao", ""),
            "duracao_minutos": 30,
            "lembrete_enviado": False,
            "recorrente": False,
        }

        agendamento_id = agendamento_repo.criar_agendamento(agendamento_data)
        state["agendamento"] = {"id": agendamento_id, "data": data_agendamento}
    except Exception:
        state["agendamento"] = None

    return state


def emitir_alertas(state: dict) -> dict:
    alertas = []
    data_ultima_consulta = state.get("data_ultima_consulta")
    exames = state.get("exames", [])
    tratamento_necessario = state.get("tratamento_necessario", False)

    if data_ultima_consulta:
        dias_desde = (datetime.now().date() - data_ultima_consulta).days
        if dias_desde > 180:
            alertas.append(f"Paciente sem consulta há {dias_desde} dias")

    if tratamento_necessario:
        alertas.append("Paciente necessita de acompanhamento profissional")

    if exames:
        ultimo_exame = exames[0]
        alertas.append(f"Último exame realizado em {ultimo_exame['data']}")

    state["alertas"] = alertas
    return state


def registrar_log_auditoria(state: dict) -> dict:
    nome = state.get("nome", "Unknown")
    ja_existe = state.get("ja_existe", False)
    tratamento_necessario = state.get("tratamento_necessario", False)

    detalhe = {
        "paciente_nome": nome,
        "paciente_existe": ja_existe,
        "tratamento_necessario": tratamento_necessario,
        "timestamp": datetime.now().isoformat(),
        "alertas": state.get("alertas", []),
        "agendamento_id": state.get("agendamento", {}).get("id"),
    }

    try:
        entrada_log = EntradaLog(
            sessao_id="default_session",
            acao="analise_paciente",
            detalhe=detalhe,
        )
        log_id = log_repo.registrar_log(entrada_log)
        state["log_id"] = log_id
    except Exception:
        state["log_id"] = None

    mensagem = f"Análise concluída para {nome}. "
    if state.get("agendamento"):
        mensagem += f"Consulta agendada para {state['agendamento']['data']}. "
    if state.get("alertas"):
        mensagem += f"Alertas: {', '.join(state['alertas'])}"

    state["mensagem_final"] = mensagem
    return state


def verificar_paciente_existe(state: dict) -> str:
    return "paciente_existe" if state.get("ja_existe") else "paciente_nao_existe"


def verificar_tratamento_necessario(state: dict) -> str:
    return (
        "tratamento_necessario"
        if state.get("tratamento_necessario")
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
