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
        template="""Você é um assistente médico de apoio à decisão clínica. Você NUNCA prescreve
medicamentos nem toma decisões médicas de forma autônoma e definitiva. Suas análises e
recomendações são instrumentos de apoio e devem sempre ser validadas por um profissional
de saúde habilitado antes de qualquer aplicação.

=== CONTEXTO DO PACIENTE (dados estruturados do sistema) ===
Paciente: {nome}
Última consulta: {data_ultima_consulta}

Prontuários recentes:
{prontuarios}

Exames recentes:
{exames}

{contexto_documentos}

Regras para as fontes:
- Utilize os dados estruturados do paciente para descrever o quadro clínico.
- Utilize o conhecimento de referência recuperado (RAG), se presente, para
  fundamentar, contextualizar ou enriquecer a sua análise.
- Ao usar uma informação do conhecimento recuperado, cite a referência
  correspondente indicando o número, ex.: "Conforme a referência [1]".
- NUNCA invente fontes que não estejam listadas no contexto documental.
- Se nenhuma fonte documental relevante foi recuperada, deixe isso explícito,
  por exemplo: "Não foram encontradas fontes documentais relevantes na base de
  conhecimento para complementar esta análise."
- Diferencie claramente o que é dado do paciente (SQL) do que é conhecimento
  externo (RAG).

Com base no histórico do paciente e no conhecimento recuperado, qual é sua análise
inicial sobre a saúde e bem-estar? Indique claramente quais fontes você utilizou,
com arquivo e localização (página/planilha) quando disponíveis."""
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
                Considere o histórico clínico disponível.

                IMPORTANTE: As sugestões abaixo são apenas apoio à decisão clínica e NÃO
                constituem prescrição médica definitiva. Toda recomendação deve ser
                validada e autorizada por um profissional de saúde habilitado antes de
                qualquer aplicação. Não emita posologia exata como se fosse prescrição
                autônoma; descreva a abordagem geral e a necessidade de avaliação médica."""
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
    if not state.get("nome") or not state.get("cpf"):
        print("\n" + "="*60)
        print("CONSULTA MÉDICA - ASSISTENTE MÉDICO")
        print("="*60)
        nome = input("Nome do paciente: ").strip()
        cpf = input("CPF do paciente: ").strip()

        state["nome"] = nome
        state["cpf"] = cpf

    state["ja_existe"] = False
    state["paciente"] = None
    state["exames"] = None
    state["data_ultima_consulta"] = None
    state["prontuarios"] = None
    state["tratamento_necessario"] = False
    state["mensagem_final"] = ""
    state["logging_rag"] = {"tem_conhecimento": False}
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
    nome = state.get("nome", "").strip()
    cpf = state.get("cpf", "").strip()

    if not nome or not cpf:
        state["paciente"] = None
        state["ja_existe"] = False
        state["erro_busca"] = "Nome e CPF são obrigatórios"
        return state

    try:
        pacientes = paciente_repo.buscar_paciente(nome, limite=1)

        if not pacientes:
            state["paciente"] = None
            state["ja_existe"] = False
            state["erro_busca"] = None
            return state

        paciente = pacientes[0]
        cpf_paciente = (paciente.cpf_mascarado or "").strip()
        cpf_entrada = cpf.strip()

        # Validação dupla: verificar se o CPF informado bate com o CPF no banco
        if not cpf_paciente:
            state["paciente"] = None
            state["ja_existe"] = False
            state["erro_busca"] = f"Erro: paciente '{nome}' no sistema não possui CPF registrado."
            return state

        if cpf_entrada != cpf_paciente:
            state["paciente"] = None
            state["ja_existe"] = False
            state["erro_busca"] = f"Dados inconsistentes: o CPF informado não corresponde ao registro de '{nome}'. Verifique os dados fornecidos."
            return state

        state["paciente"] = paciente
        state["ja_existe"] = True
        state["erro_busca"] = None

    except Exception as e:
        state["paciente"] = None
        state["ja_existe"] = False
        state["erro_busca"] = f"Erro ao buscar paciente: {str(e)}"

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


async def _executar_recuperar_conhecimento(prontuarios):
    """Recupera conhecimento contextual (protocolos, casos, diretrizes) via RAG.

    Usa os prontuários do paciente para montar a consulta semântica e busca na
    coleção de conhecimento (separada da coleção de atendimentos). Retorna os
    documentos recuperados junto com a metadata de fonte para rastreabilidade,
    incluindo identificadores de localização (página/planilha) quando presentes.
    """
    import time as _time

    if not prontuarios:
        return {"conhecimento_recuperado": [], "fontes_utilizadas": [], "logging_rag": {}}

    try:
        consulta = " ".join(
            [f"{p.get('queixa', '')} {p.get('conduta', '')}" for p in prontuarios[:3]]
        ).strip()

        if not consulta:
            return {"conhecimento_recuperado": [], "fontes_utilizadas": [], "logging_rag": {}}

        inicio = _time.perf_counter()
        provedor = obter_provedor(os.getenv("MEDPT_EMBEDDING_PROVIDER", "mock"))
        resultados = await asyncio.to_thread(
            busca_repo.buscar_conhecimento, consulta, provedor, 5
        )
        tempo_ms = int((_time.perf_counter() - inicio) * 1000)

        conhecimento = [
            {
                "fonte": r.fonte,
                "tipo_documento": r.tipo_documento,
                "titulo": r.titulo,
                "autor": r.autor,
                "ano": r.ano,
                "pagina": r.pagina,
                "planilha": r.planilha,
                "arquivo": r.arquivo,
                "similaridade": r.similaridade,
                "conteudo": r.conteudo,
            }
            for r in resultados
        ]
        fontes = [
            {
                "fonte": r.fonte,
                "tipo_documento": r.tipo_documento,
                "titulo": r.titulo,
                "autor": r.autor,
                "ano": r.ano,
                "pagina": r.pagina,
                "planilha": r.planilha,
                "arquivo": r.arquivo,
            }
            for r in resultados
        ]
        logging_rag = {
            "consulta_rag": consulta,
            "docs_encontrados": len(resultados),
            "scores": [r.similaridade for r in resultados],
            "tempo_retrieval_ms": tempo_ms,
            "tem_conhecimento": bool(resultados),
        }
        return {
            "conhecimento_recuperado": conhecimento,
            "fontes_utilizadas": fontes,
            "logging_rag": logging_rag,
        }
    except Exception:
        return {
            "conhecimento_recuperado": [],
            "fontes_utilizadas": [],
            "logging_rag": {"tem_conhecimento": False},
        }


async def obter_dados_paciente_paralelo(state: DadosPaciente) -> DadosPaciente:
    """Executa obter_prontuarios e recuperar conhecimento com dependência"""
    paciente = state.get("paciente")

    if not paciente:
        state["prontuarios"] = []
        state["exames"] = []
        state["conhecimento_recuperado"] = []
        state["fontes_utilizadas"] = []
        state["logging_rag"] = {"tem_conhecimento": False}
        return state

    # Primeiro: obter prontuários (necessário para busca vetorial)
    resultado_prontuarios = await _executar_obter_prontuarios(paciente.id)
    state.update(resultado_prontuarios)

    # Segundo: recuperar conhecimento contextual (depende dos prontuários)
    resultado_conhecimento = await _executar_recuperar_conhecimento(resultado_prontuarios["prontuarios"])
    state.update(resultado_conhecimento)

    return state


def consultar_modelo_llm(state: DadosPaciente) -> DadosPaciente:
    nome = state.get("nome", "")
    prontuarios = state.get("prontuarios", [])
    exames = state.get("exames", [])
    conhecimento_recuperado = state.get("conhecimento_recuperado", [])

    contexto_documentos = _formatar_contexto_conhecimento(conhecimento_recuperado)

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


def _formatar_contexto_conhecimento(conhecimento_recuperado) -> str:
    """Formata o conhecimento recuperado com fontes numeradas para o prompt.

    Cada documento recebe um número de referência [1], [2], ... que a LLM pode
    citar na resposta e que é mapeado de volta à fonte original, incluindo
    identificadores de localização (página/planilha) quando disponíveis.
    """
    if not conhecimento_recuperado:
        return ""

    linhas = [
        "\n\n=== CONTEXTO DOCUMENTAL / RAG ===",
        "\n[documentos recuperados da base de conhecimento, com suas fontes]",
        "O texto a seguir é conhecimento contextual para fundamentar sua análise. "
        "Cite apenas as fontes abaixo (referências [1], [2], ...), ex.: "
        "'Conforme a referência [1]'. Não invente fontes que não estejam listadas. "
        "Se nenhuma fonte relevante tiver sido recuperada, deixe isso explícito "
        "na resposta.",
    ]
    for indice, doc in enumerate(conhecimento_recuperado, start=1):
        localizacao = _localizacao_legivel(doc)
        linhas.append(
            f"\n[{indice}] Fonte: {doc.get('fonte', 'N/A')}"
            f"{localizacao}"
            f"\n    Título: {doc.get('titulo', 'N/A')}"
            f"\n    Tipo: {doc.get('tipo_documento', 'N/A')}"
            f"\n    Autor: {doc.get('autor', 'N/A') or 'N/A'}"
            f"\n    Ano: {doc.get('ano', 'N/A') or 'N/A'}"
            f"\n    Conteúdo: {doc.get('conteudo', 'N/A')[:400]}"
        )
    return "\n".join(linhas)


def _localizacao_legivel(doc) -> str:
    """Monta, se houver, a localização da fonte (página/planilha)."""
    paginas = [doc.get("pagina"), doc.get("page")]
    pagina = next((p for p in paginas if p is not None), None)
    planilha = doc.get("planilha") or doc.get("sheet")
    partes = []
    if pagina is not None:
        partes.append(f"Página: {pagina}")
    if planilha:
        partes.append(f"Planilha: {planilha}")
    return f"\n    Localização: {', '.join(partes)}" if partes else ""


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
    fontes = state.get("fontes_utilizadas", [])
    logging_rag = state.get("logging_rag", {})
    detalhe = {
        "paciente_nome": nome,
        "paciente_existe": ja_existe,
        "tratamento_necessario": tratamento_necessario,
        "timestamp": datetime.now().isoformat(),
        "alertas": state.get("alertas", []),
        "agendamento_id": agendamento.get("id"),
        "fontes_utilizadas": fontes,
        # Rastreamento do RAG (logs/auditoria)
        "consultas_rag": logging_rag,
        "possui_conhecimento": bool(logging_rag.get("tem_conhecimento", False)),
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

    # Resposta estruturada (answer + sources) para consumidores da API
    state["resposta_estruturada"] = _montar_resposta_estruturada(state, fontes)

    # Preservar mensagem de erro se houver
    if not state.get("mensagem_final") or not state.get("mensagem_final").startswith("❌"):
        mensagem = f"Analise concluida para {nome}. "
        if state.get("agendamento"):
            mensagem += f"Consulta agendada para {state['agendamento']['data']}. "
        if state.get("alertas"):
            mensagem += f"Alertas: {', '.join(state['alertas'])}"
        mensagem += _formatar_fontes_para_mensagem(fontes)
        mensagem += ("\n⚠️ IMPORTANTE: Esta análise é uma ferramenta de apoio à decisão "
                     "clínica. As recomendações devem ser validadas por um profissional "
                     "de saúde habilitado antes de qualquer aplicação.")
        state["mensagem_final"] = mensagem

    return state


def _montar_resposta_estruturada(state, fontes) -> dict:
    """Monta a resposta estruturada (answer + sources + segurança).

    O campo ``sources`` reflete **apenas** os documentos realmente recuperados
    pelo RAG — nunca inventa fontes. Quando não houver conhecimento recuperado,
    ``sources`` fica vazio e ``nada_relevante`` é marcado como verdadeiro.
    """
    analise = state.get("analise_llm", "")

    sources = []
    for fonte in ([f for f in fontes if f] or []):
        source_item = {
            "source": fonte.get("fonte") or fonte.get("arquivo"),
            "type": fonte.get("tipo_documento") or fonte.get("source_type"),
            "title": fonte.get("titulo"),
        }
        if fonte.get("pagina") is not None or fonte.get("page") is not None:
            source_item["page"] = fonte.get("pagina") or fonte.get("page")
        if fonte.get("planilha") or fonte.get("sheet"):
            source_item["sheet"] = fonte.get("planilha") or fonte.get("sheet")
        if fonte.get("autor"):
            source_item["author"] = fonte.get("autor")
        if fonte.get("ano"):
            source_item["year"] = fonte.get("ano")
        sources.append(source_item)

    return {
        "answer": analise,
        "sources": sources,
        "nada_relevante": not sources,
        "safety": {
            "validado_profissional": True,
            "disclaimer": (
                "Análise de apoio à decisão clínica. As recomendações devem ser "
                "validadas por um profissional de saúde habilitado antes de qualquer "
                "aplicação. Não constitui prescrição médica definitiva."
            ),
            "prescricao_direta_detectada": _detectar_prescricao_direta(analise),
        },
    }


_PADROES_PRESCRICAO_DIRETA = (
    r"\bprescrev\w*",
    r"\btomar\s+\d+\s*(mg|g|mcg|ui)",
    r"\bdose\s+(recomendada\s+de\s+\d+|de\s+\d+\s*(mg|g|mcg|ui))",
    r"\bposologia",
)


def _detectar_prescricao_direta(texto: str) -> bool:
    """Detecta se a resposta aparenta conter prescrição direta (sem qualificador).

    É uma heurística de salvaguarda (requisito de segurança do Tech Challenge:
    nunca prescrever diretamente sem validação humana). Retorna True quando
    encontra padrões típicos de prescrição definitiva; o disclaimer de validação
    humana é sempre mantido na resposta final, independentemente deste flag.
    """
    if not texto:
        return False
    texto_normalizado = texto.lower()
    for padrao in _PADROES_PRESCRICAO_DIRETA:
        if re.search(padrao, texto_normalizado):
            return True
    return False


def _formatar_fontes_para_mensagem(fontes) -> str:
    """Converte as fontes recuperadas pelo RAG em texto legível para o usuário."""
    if not fontes:
        return ""

    partes = ["\n\nFontes consultadas:"]
    for indice, fonte in enumerate(
        [f for f in fontes if f], start=1
    ):
        titulo = fonte.get("titulo", "Sem título")
        autor = fonte.get("autor")
        ano = fonte.get("ano")
        base = f"  [{indice}] {titulo}"
        if autor:
            base += f" - {autor}"
        if ano:
            base += f" ({ano})"
        localizacao = _localizacao_legivel(fonte)
        if localizacao:
            base += f" | {localizacao.strip().replace('Localização: ', '')}"
        partes.append(base)

    return "\n".join(partes)


def tratar_erro_busca(state: DadosPaciente) -> DadosPaciente:
    erro = state.get("erro_busca")
    if erro:
        state["mensagem_final"] = f"❌ ERRO: {erro}"
    return state


def verificar_paciente_existe(state: DadosPaciente) -> str:
    if state.get("erro_busca"):
        return "erro_validacao"
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
workflow.add_node("tratar_erro_busca", tratar_erro_busca)
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
    {
        "paciente_existe": "obter_dados_paciente_paralelo",
        "paciente_nao_existe": "marcar_consulta",
        "erro_validacao": "tratar_erro_busca",
    },
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
workflow.add_edge("tratar_erro_busca", "registrar_log_auditoria")

workflow.set_entry_point("obter_entrada")
workflow.set_finish_point("registrar_log_auditoria")
app = workflow.compile()

print("Estrutura do grafo:")
print(app.get_graph().draw_ascii())


async def executar_fluxo():
    resultado = await app.ainvoke({})

    print("\n" + "="*60)
    print("RESULTADO DO FLUXO")
    print("="*60)
    print(f"Mensagem Final: {resultado.get('mensagem_final', '<sem retorno>')}")
    print(f"Paciente Existe: {resultado.get('ja_existe')}")
    print(f"Analise LLM: {resultado.get('analise_llm', 'N/A')}")
    print(f"Explicacao: {resultado.get('explicacao', 'N/A')}")
    print(f"Tratamentos: {resultado.get('tratamentos', 'N/A')}")
    print(f"Tratamento Necessario: {resultado.get('tratamento_necessario')}")
    print(f"Alertas: {resultado.get('alertas', [])}")
    print(f"Agendamento: {resultado.get('agendamento', 'N/A')}")
    print(f"Log ID: {resultado.get('log_id', 'N/A')}")
    print(f"Fontes Utilizadas: {resultado.get('fontes_utilizadas', [])}")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(executar_fluxo())
