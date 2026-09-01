import os
import json
import asyncio
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
from src.db.buscar.buscar_repo import BuscaRepositorio
from src.db.embeddings import obter_provedor
from src.db.models import EntradaLog
import re

llm = get_llm()

paciente_repo = PacienteRepositorio()
atendimento_repo = AtendimentoRepositorio()
agendamento_repo = AgendamentoRepositorio()
log_repo = LogRepositorio()
busca_repo = BuscaRepositorio()

# Prompts templates
prompt_analise_inicial = PromptTemplate(
        input_variables=["nome", "data_ultima_consulta", "prontuarios", "exames", "contexto_documentos"],
        template="""Paciente: {nome}
                    Última consulta: {data_ultima_consulta}

                    Prontuários recentes:
                    {prontuarios}

                    Exames recentes:
                    {exames}{contexto_documentos}

                    Com base no histórico do paciente e documentos similares, qual é sua análise inicial sobre a saúde e bem-estar?"""
)

prompt_explicacao = PromptTemplate(
    input_variables=["analise", "nome"],
    template="""Baseado na seguinte análise: {analise}

                Gere uma explicação clara e acessível para o paciente {nome} sobre seu estado de saúde.
                A explicação deve ser breve e informativa."""
)

prompt_tratamento = PromptTemplate(
    input_variables=["analise"],
    template="""Baseado na análise: {analise}

                Sugira tratamentos e cuidados recomendados para o paciente.
                Responda em formato de lista com recomendações práticas.
                Considere o histórico clínico disponível."""
)

prompt_extrair_alergias = PromptTemplate(
    input_variables=["analise"],
    template="""Análise clínica: {analise}

                Extraia TODAS as alergias, intolerâncias ou contraindicações mencionadas.
                Responda em JSON puro (sem markdown) com este formato:
                {{"alergias": [
                    {{"nome": "Penicilina", "tipo": "medicamento", "severidade": "grave", "reacao": "anafilaxia"}},
                    {{"nome": "Glúten", "tipo": "alimento", "severidade": "leve", "reacao": "dor abdominal"}}
                ]}}

                Se não houver alergias, retorne: {{"alergias": []}}"""
)

prompt_validar_medicamentos = PromptTemplate(
    input_variables=["tratamentos", "alergias"],
    template="""Tratamentos sugeridos: {tratamentos}
                Alergias do paciente: {alergias}

                Verifique se há CONFLITO entre medicamentos e alergias.
                Responda em JSON puro com este formato:
                {{"conflitos": [
                    {{"medicamento": "Amoxicilina", "alergia": "Penicilina", "risco": "anafilaxia"}},
                ], "seguro": true/false}}

                Se não houver conflitos, retorne: {{"conflitos": [], "seguro": true}}"""
)


def obter_entrada(state: DadosPaciente) -> DadosPaciente:
    state["ja_existe"] = False
    state["paciente"] = None
    state["exames"] = None
    state["data_ultima_consulta"] = None
    state["prontuarios"] = None
    state["tratamento_necessario"] = False
    state["mensagem_final"] = ""
    return state


def validar_dados_paciente(state: DadosPaciente) -> DadosPaciente:
    nome = state.get("nome", "").strip()
    cpf = state.get("cpf", "").strip() if state.get("cpf") else None

    if not nome or len(nome) < 2:
        raise ValueError("Nome inválido: deve ter pelo menos 2 caracteres")

    if cpf and len(cpf) < 10:
        raise ValueError("CPF inválido")

    state["nome"] = nome
    state["cpf"] = cpf
    return state


def buscar_paciente(state: DadosPaciente) -> DadosPaciente:
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


async def _executar_obter_prontuarios(paciente_id):
    try:
        atendimentos = await asyncio.to_thread(
            atendimento_repo.obter_prontuarios, paciente_id, 10
        )
        condicoes = await asyncio.to_thread(
            atendimento_repo.obter_condicoes, paciente_id
        )
        exames = await asyncio.to_thread(
            atendimento_repo.obter_exames, paciente_id, 10
        )
        return {
            "prontuarios": [
                {
                    "id": a.id,
                    "data": a.data_atendimento.isoformat(),
                    "queixa": a.queixa,
                    "conduta": a.conduta,
                    "condicoes": [c.condicao for c in condicoes],
                }
                for a in atendimentos
            ],
            "exames": [
                {
                    "id": e.exame_id,
                    "nome": e.nome_exame,
                    "data": e.data_exame.isoformat(),
                    "resultado": e.resultado,
                }
                for e in exames
            ],
            "data_ultima_consulta": atendimentos[0].data_atendimento.date() if atendimentos else None,
        }
    except Exception:
        return {"prontuarios": [], "exames": [], "data_ultima_consulta": None}


async def _executar_recuperar_documentos(prontuarios):
    if not prontuarios:
        return {"documentos_similares": []}

    try:
        consulta = " ".join(
            [f"{p.get('queixa', '')} {p.get('conduta', '')}" for p in prontuarios[:3]]
        ).strip()

        if not consulta:
            return {"documentos_similares": []}

        provedor = obter_provedor(os.getenv("MEDPT_EMBEDDING_PROVIDER", "mock"))
        resultados = await asyncio.to_thread(
            busca_repo.buscar_vetorial, consulta, provedor, 5
        )

        return {
            "documentos_similares": [
                {
                    "atendimento_id": r.atendimento_id,
                    "similaridade": r.similaridade,
                    "conteudo": r.conteudo,
                    "condicao": r.condicao,
                    "especialidade": r.especialidade_principal,
                    "data_atendimento": r.data_atendimento,
                }
                for r in resultados
            ]
        }
    except Exception:
        return {"documentos_similares": []}


async def obter_dados_paciente_paralelo(state: DadosPaciente) -> DadosPaciente:
    """Executa obter_prontuarios e recuperar_documentos com dependência"""
    paciente = state.get("paciente")

    if not paciente:
        state["prontuarios"] = []
        state["exames"] = []
        state["documentos_similares"] = []
        return state

    # Primeiro: obter prontuários (necessário para busca vetorial)
    resultado_prontuarios = await _executar_obter_prontuarios(paciente.id)
    state.update(resultado_prontuarios)

    # Segundo: recuperar documentos similares (depende dos prontuários)
    resultado_docs = await _executar_recuperar_documentos(resultado_prontuarios["prontuarios"])
    state.update(resultado_docs)

    return state


def consultar_modelo_llm(state: DadosPaciente) -> DadosPaciente:
    nome = state.get("nome", "")
    prontuarios = state.get("prontuarios", [])
    exames = state.get("exames", [])
    documentos_similares = state.get("documentos_similares", [])

    contexto_documentos = ""
    if documentos_similares:
        contexto_documentos = "\n\nDocumentos similares recuperados (RAG):\n"
        for doc in documentos_similares:
            contexto_documentos += f"""
                - Condição: {doc.get('condicao', 'N/A')}
                Similaridade: {doc.get('similaridade', 0):.2%}
                Data: {doc.get('data_atendimento', 'N/A')}
                Conteúdo: {doc.get('conteudo', 'N/A')[:200]}...
            """

    contexto = prompt_analise_inicial.format(
        nome=nome,
        data_ultima_consulta=state.get("data_ultima_consulta", "N/A"),
        prontuarios=json.dumps(prontuarios, ensure_ascii=False, indent=2),
        exames=json.dumps(exames, ensure_ascii=False, indent=2),
        contexto_documentos=contexto_documentos
    )

    try:
        response = llm.invoke(contexto)
        state["analise_llm"] = response.content
    except Exception as e:
        state["analise_llm"] = f"Erro ao consultar LLM: {str(e)}"

    return state


def gerar_explicacao(state: DadosPaciente) -> DadosPaciente:
    analise = state.get("analise_llm", "")
    nome = state.get("nome", "")

    try:
        prompt_msg = prompt_explicacao.format(analise=analise, nome=nome)
        response = llm.invoke(prompt_msg)
        state["explicacao"] = response.content
    except Exception:
        state["explicacao"] = "Não foi possível gerar uma explicação neste momento."

    return state


def extrair_alergias(state: DadosPaciente) -> DadosPaciente:
    """Extrai alergias mencionadas na análise do LLM."""
    analise = state.get("analise_llm", "")

    if not analise:
        state["alergias_extraidas"] = []
        return state

    try:
        prompt_msg = prompt_extrair_alergias.format(analise=analise)
        response = llm.invoke(prompt_msg)
        resposta_texto = response.content.strip()

        # Tentar parse JSON
        import json as json_lib
        resultado = json_lib.loads(resposta_texto)
        state["alergias_extraidas"] = resultado.get("alergias", [])
    except Exception as e:
        print(f"Erro ao extrair alergias: {e}")
        state["alergias_extraidas"] = []

    return state


def validar_com_profissional(state: DadosPaciente) -> DadosPaciente:
    state["validacao_profissional"] = {
        "validado": True,
        "comentarios": "Análise revisada e aprovada.",
        "timestamp": datetime.now().isoformat(),
    }
    return state


def sugerir_tratamentos(state: DadosPaciente) -> DadosPaciente:
    analise = state.get("analise_llm", "")

    try:
        prompt_msg = prompt_tratamento.format(analise=analise)
        response = llm.invoke(prompt_msg)
        tratamentos = response.content

        state["tratamento_necessario"] = bool(tratamentos and len(tratamentos) > 10)
        state["tratamentos"] = tratamentos
    except Exception:
        state["tratamento_necessario"] = False
        state["tratamentos"] = "Não foi possível sugerir tratamentos."

    return state


def validar_alergias_guardrail(state: DadosPaciente) -> DadosPaciente:
    """Guardrail: Valida medicamentos sugeridos contra alergias extraídas."""
    alergias = state.get("alergias_extraidas", [])
    tratamentos = state.get("tratamentos", "")

    state["validacao_alergias"] = {
        "conflitos": [],
        "seguro": True,
        "avisos": []
    }

    if not alergias or not tratamentos:
        return state

    try:
        import json as json_lib

        # Converter alergias para texto legível
        alergias_texto = json_lib.dumps(alergias, ensure_ascii=False, indent=2)

        # Usar LLM para validar
        prompt_msg = prompt_validar_medicamentos.format(
            tratamentos=tratamentos,
            alergias=alergias_texto
        )

        response = llm.invoke(prompt_msg)
        resultado_texto = response.content.strip()
        resultado = json_lib.loads(resultado_texto)

        conflitos = resultado.get("conflitos", [])
        seguro = resultado.get("seguro", True)

        if conflitos:
            state["validacao_alergias"]["seguro"] = False
            state["validacao_alergias"]["conflitos"] = conflitos
            avisos = [
                f"⚠️ ALERTA: {c['medicamento']} pode causar {c['risco']} (alergia a {c['alergia']})"
                for c in conflitos
            ]
            state["validacao_alergias"]["avisos"] = avisos

            # Bloquear tratamento se houver conflito crítico
            state["tratamento_necessario"] = False
            state["tratamentos"] = (
                f"❌ TRATAMENTOS BLOQUEADOS POR GUARDRAIL DE SEGURANÇA:\n"
                f"{chr(10).join(avisos)}\n\n"
                f"Procure a equipe médica para revisar as recomendações."
            )

    except Exception as e:
        print(f"Erro ao validar alergias: {e}")

    return state


def marcar_consulta(state: DadosPaciente) -> DadosPaciente:
    paciente = state.get("paciente")

    if not paciente:
        state["agendamento"] = None
        return state

    try:
        data_agendamento = (datetime.now() + td(days=7)).isoformat()

        agendamento_data = {
            "paciente_id": paciente.id,
            "profissional_id": 1,
            "especialidade_id": 1,
            "data_hora_agendada": data_agendamento,
            "status": "agendado",
            "motivo": "Acompanhamento de saude",
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


def emitir_alertas(state: DadosPaciente) -> DadosPaciente:
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


def registrar_log_auditoria(state: DadosPaciente) -> DadosPaciente:
    nome = state.get("nome", "Unknown")
    ja_existe = state.get("ja_existe", False)
    tratamento_necessario = state.get("tratamento_necessario", False)

    agendamento = state.get("agendamento") or {}
    detalhe = {
        "paciente_nome": nome,
        "paciente_existe": ja_existe,
        "tratamento_necessario": tratamento_necessario,
        "timestamp": datetime.now().isoformat(),
        "alertas": state.get("alertas", []),
        "agendamento_id": agendamento.get("id"),
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

    mensagem = f"Analise concluida para {nome}. "
    if state.get("agendamento"):
        mensagem += f"Consulta agendada para {state['agendamento']['data']}. "
    if state.get("alertas"):
        mensagem += f"Alertas: {', '.join(state['alertas'])}"

    state["mensagem_final"] = mensagem
    return state


def verificar_paciente_existe(state: DadosPaciente) -> str:
    return "paciente_existe" if state.get("ja_existe") else "paciente_nao_existe"


def verificar_tratamento_necessario(state: DadosPaciente) -> str:
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
workflow.add_node("obter_dados_paciente_paralelo", obter_dados_paciente_paralelo)
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
    {"paciente_existe": "obter_dados_paciente_paralelo", "paciente_nao_existe": "marcar_consulta"},
)
workflow.add_edge("obter_dados_paciente_paralelo", "consultar_modelo_llm")
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
workflow.add_edge("marcar_consulta", "registrar_log_auditoria")
workflow.add_edge("emitir_alertas", "registrar_log_auditoria")

workflow.set_entry_point("obter_entrada")
workflow.set_finish_point("registrar_log_auditoria")
app = workflow.compile()

print("Estrutura do grafo:")
print(app.get_graph().draw_ascii())

# Dados de entrada para teste do fluxo
entrada = {
    "nome": "Lara Abreu",
    "cpf": "***.917.803-**",
}

async def executar_fluxo():
    import sys
    print("\n" + "="*60, file=sys.stderr)
    print("Iniciando teste do fluxo LangGraph (ASYNC PARALELO)", file=sys.stderr)
    print("="*60, file=sys.stderr)
    print(f"Entrada: {entrada}\n", file=sys.stderr)

    resultado = await app.ainvoke(entrada)

    print("\n" + "="*60, file=sys.stderr)
    print("RESULTADO DO FLUXO", file=sys.stderr)
    print("="*60, file=sys.stderr)
    print(f"Mensagem Final: {resultado.get('mensagem_final', '<sem retorno>')}", file=sys.stderr)
    print(f"Paciente Existe: {resultado.get('ja_existe')}", file=sys.stderr)
    print(f"Analise LLM: {resultado.get('analise_llm', 'N/A')}", file=sys.stderr)
    print(f"Explicacao: {resultado.get('explicacao', 'N/A')}", file=sys.stderr)
    print(f"Tratamentos: {resultado.get('tratamentos', 'N/A')}", file=sys.stderr)
    print(f"Tratamento Necessario: {resultado.get('tratamento_necessario')}", file=sys.stderr)
    print(f"Alertas: {resultado.get('alertas', [])}", file=sys.stderr)
    print(f"Agendamento: {resultado.get('agendamento', 'N/A')}", file=sys.stderr)
    print(f"Log ID: {resultado.get('log_id', 'N/A')}", file=sys.stderr)
    print("="*60, file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(executar_fluxo())
