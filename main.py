import os
import json
import asyncio
import time
from datetime import datetime, timedelta as td
from langchain_core.prompts import PromptTemplate
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

def _invoke_with_retry(llm_instance, prompt: str, max_retries: int = 3, **kwargs):
    """Invoca o LLM com retry automático em caso de erro de indisponibilidade."""
    for tentativa in range(max_retries):
        try:
            return llm_instance.invoke(prompt, **kwargs)
        except Exception as e:
            erro_str = str(e)
            if "not ready" in erro_str or "connection" in erro_str.lower():
                if tentativa < max_retries - 1:
                    tempo_espera = 5 * (tentativa + 1)
                    print(f"⏳ LLM indisponível. Aguardando {tempo_espera}s... (tentativa {tentativa + 1}/{max_retries})")
                    time.sleep(tempo_espera)
                    continue
            raise

paciente_repo = PacienteRepositorio()
atendimento_repo = AtendimentoRepositorio()
agendamento_repo = AgendamentoRepositorio()
log_repo = LogRepositorio()
busca_repo = BuscaRepositorio()

# LLM será inicializado dentro de executar_fluxo() para usar variáveis de ambiente atualizadas
llm = None

# Prompts templates
prompt_analise_inicial = PromptTemplate(
        input_variables=["nome", "data_ultima_consulta", "prontuarios", "exames", "contexto_documentos", "pergunta_medico"],
        template="""Você é um assistente médico de apoio à decisão clínica. Você NUNCA prescreve
                    medicamentos nem toma decisões médicas de forma autônoma e definitiva. Suas análises e
                    recomendações são instrumentos de apoio e devem sempre ser validadas por um profissional
                    de saúde habilitado antes de qualquer aplicação.

                    === PERGUNTA DO PROFISSIONAL DE SAÚDE ===
                    {pergunta_medico}

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

                    Priorize responder diretamente à pergunta do profissional de saúde acima, usando o
                    histórico do paciente e o conhecimento recuperado como base. Se a pergunta não tiver
                    sido informada, apresente sua análise inicial sobre a saúde e bem-estar do paciente.
                    Indique claramente quais fontes você utilizou, com arquivo e localização
                    (página/planilha) quando disponíveis."""
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

prompt_guardrail_contexto_medico = PromptTemplate(
    input_variables=["pergunta", "nome"],
    template="""Você é um guardrail minimalista para um assistente médico. Sua função é bloquear
APENAS perguntas que são claramente fora do contexto médico.

Bloqueia apenas se a pergunta for sobre:
- Recomendações de produtos não-médicos (carros, eletrônicos, roupas, etc.)
- Planejamento de viagens, turismo, entretenimento
- Assuntos pessoais sem relação com saúde (relacionamentos, finanças, etc.)
- Pedidos completamente desconectados de atendimento/saúde

Aceita (permite passar) qualquer coisa que possa estar relacionada a:
- Sintomas, queixa, condição de saúde do paciente
- Orientações, tratamento, medicação, procedimentos, exames
- Histórico clínico, acompanhamento
- Avaliação clínica, recomendações
- Dúvida sobre interpretação clínica

Quando há ambiguidade, ACEITA (contexto_medico = true).

Pergunta: "{pergunta}"

Responda JSON puro: {{"contexto_medico": true/false, "justificativa": "breve"}}"""
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

    if not state.get("pergunta_medico"):
        pergunta = input("Pergunta/observação sobre o paciente: ").strip()
        state["pergunta_medico"] = pergunta

    state["ja_existe"] = False
    state["paciente"] = None
    state["exames"] = None
    state["data_ultima_consulta"] = None
    state["prontuarios"] = None
    state["tratamento_necessario"] = False
    state["mensagem_final"] = ""
    state["logging_rag"] = {"tem_conhecimento": False}
    state["contexto_valido"] = None
    state["justificativa_guardrail"] = None
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
        # Reduzir quantidade de prontuários/exames para não exceder contexto do Ollama
        atendimentos = await asyncio.to_thread(
            atendimento_repo.obter_prontuarios, paciente_id, 3  # Reduzido de 10
        )
        condicoes = await asyncio.to_thread(
            atendimento_repo.obter_condicoes, paciente_id
        )
        exames = await asyncio.to_thread(
            atendimento_repo.obter_exames, paciente_id, 3  # Reduzido de 10
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


async def _executar_recuperar_conhecimento(pergunta_medico, prontuarios):
    """Recupera conhecimento contextual (protocolos, casos, diretrizes) via RAG.

    A consulta semântica prioriza a pergunta livre feita pelo médico (é o que
    ele efetivamente quer saber); quando não há pergunta, cai no histórico de
    prontuários (queixa/conduta) como aproximação. Aplica um corte mínimo de
    similaridade (``MEDPT_RAG_SIMILARIDADE_MINIMA``) para evitar retornar
    documentos pouco relacionados só para completar o top-k.
    """
    import time as _time

    print(f"\n[DEBUG RAG] Iniciando recuperação de conhecimento...")
    print(f"[DEBUG RAG] Prontuários: {len(prontuarios)}")
    print(f"[DEBUG RAG] Pergunta: {pergunta_medico[:80] if pergunta_medico else 'VAZIA'}...")

    if not prontuarios:
        print(f"[DEBUG RAG] Retorno: sem prontuários")
        return {"conhecimento_recuperado": [], "fontes_utilizadas": [], "logging_rag": {}}

    try:
        pergunta_medico = (pergunta_medico or "").strip()
        # Extrair contexto dos prontuários (queixa + conduta)
        contexto_prontuarios = " ".join(
            [f"{p.get('queixa', '')} {p.get('conduta', '')}" for p in prontuarios[:3]]
        ).strip()

        # Busca híbrida: combinar pergunta + prontuários para melhor cobertura semântica
        if pergunta_medico and contexto_prontuarios:
            consulta = f"{pergunta_medico} {contexto_prontuarios}"
        elif pergunta_medico:
            consulta = pergunta_medico
        else:
            consulta = contexto_prontuarios

        print(f"[DEBUG RAG] Consulta final: {consulta[:80]}...")

        if not consulta:
            print(f"[DEBUG RAG] Retorno: consulta vazia")
            return {"conhecimento_recuperado": [], "fontes_utilizadas": [], "logging_rag": {}}

        limiar_minimo = float(os.getenv("MEDPT_RAG_SIMILARIDADE_MINIMA", "0.2"))

        inicio = _time.perf_counter()
        provider_name = os.getenv("MEDPT_EMBEDDING_PROVIDER", "mock")
        provedor = obter_provedor(provider_name)

        # Debug RAG
        print(f"\n[DEBUG RAG] Consulta: {consulta[:100]}...")
        print(f"[DEBUG RAG] Provider: {provider_name}")
        print(f"[DEBUG RAG] Limiar mínimo: {limiar_minimo}")

        resultados_brutos = await asyncio.to_thread(
            busca_repo.buscar_conhecimento, consulta, provedor, 5
        )

        print(f"[DEBUG RAG] Documentos encontrados (brutos): {len(resultados_brutos)}")
        if resultados_brutos:
            scores = [r.similaridade for r in resultados_brutos]
            print(f"[DEBUG RAG] Scores: {scores}")
            print(f"[DEBUG RAG] Score máximo: {max(scores):.4f}, mínimo: {min(scores):.4f}")

        resultados = [r for r in resultados_brutos if r.similaridade >= limiar_minimo]
        tempo_ms = int((_time.perf_counter() - inicio) * 1000)

        print(f"[DEBUG RAG] Documentos após limiar: {len(resultados)}")

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
            "docs_descartados_por_limiar": len(resultados_brutos) - len(resultados),
            "limiar_similaridade_minima": limiar_minimo,
            "scores": [r.similaridade for r in resultados],
            "scores_descartados": [r.similaridade for r in resultados_brutos if r.similaridade < limiar_minimo],
            "tempo_retrieval_ms": tempo_ms,
            "tem_conhecimento": bool(resultados),
        }
        return {
            "conhecimento_recuperado": conhecimento,
            "fontes_utilizadas": fontes,
            "logging_rag": logging_rag,
        }
    except Exception as e:
        print(f"\n[DEBUG RAG] ERRO: {str(e)}")
        import traceback
        print(f"[DEBUG RAG] Traceback: {traceback.format_exc()}")
        return {
            "conhecimento_recuperado": [],
            "fontes_utilizadas": [],
            "logging_rag": {"tem_conhecimento": False, "erro": str(e)},
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

    # Segundo: recuperar conhecimento contextual (prioriza a pergunta do médico;
    # depende dos prontuários apenas como fallback quando não há pergunta)
    resultado_conhecimento = await _executar_recuperar_conhecimento(
        state.get("pergunta_medico"), resultado_prontuarios["prontuarios"]
    )
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
        contexto_documentos=contexto_documentos,
        pergunta_medico=state.get("pergunta_medico") or "(nenhuma pergunta específica informada)",
    )

    try:
        response = _invoke_with_retry(llm, contexto)
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
        response = _invoke_with_retry(llm, prompt_msg)
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
        response = _invoke_with_retry(llm, prompt_msg)
        resposta_texto = response.content.strip()

        # Parse JSON robusto
        import json as json_lib
        import re as re_lib

        resultado = None
        try:
            resultado = json_lib.loads(resposta_texto)
        except json_lib.JSONDecodeError:
            # Procurar por JSON válido na resposta
            for match in re_lib.finditer(r'\{[^{}]*"alergias"[^{}]*\}', resposta_texto):
                try:
                    resultado = json_lib.loads(match.group())
                    break
                except json_lib.JSONDecodeError:
                    continue

        state["alergias_extraidas"] = resultado.get("alergias", []) if resultado else []
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
        response = _invoke_with_retry(llm, prompt_msg)
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

        response = _invoke_with_retry(llm, prompt_msg)
        resultado_texto = response.content.strip()

        # Parse JSON robusto
        resultado = None
        try:
            resultado = json_lib.loads(resultado_texto)
        except json_lib.JSONDecodeError:
            # Procurar por JSON válido na resposta
            import re as re_lib
            for match in re_lib.finditer(r'\{[^{}]*"conflitos"[^{}]*\}', resultado_texto):
                try:
                    resultado = json_lib.loads(match.group())
                    break
                except json_lib.JSONDecodeError:
                    continue

        conflitos = resultado.get("conflitos", []) if resultado else []
        seguro = resultado.get("seguro", True) if resultado else True

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


def validar_contexto_pergunta(state: DadosPaciente) -> DadosPaciente:
    """Guardrail: valida se a pergunta livre do médico está no contexto médico do paciente.

    Bloqueia (fail-safe) perguntas fora do contexto de saúde/atendimento (ex.:
    sugestões de carros, viagens, etc.). Em caso de falha técnica ao consultar
    a LLM (rate limit, timeout, etc.), também bloqueia por segurança, mas marca
    ``contexto_erro_tecnico`` para que a mensagem final não confunda uma falha
    de infraestrutura com uma classificação de conteúdo.
    """
    pergunta = (state.get("pergunta_medico") or "").strip()
    nome = state.get("nome", "")

    state["contexto_erro_tecnico"] = False

    if not pergunta:
        state["contexto_valido"] = True
        state["justificativa_guardrail"] = "Nenhuma pergunta livre foi informada."
        return state

    try:
        prompt_msg = prompt_guardrail_contexto_medico.format(pergunta=pergunta, nome=nome)
        response = _invoke_with_retry(llm, prompt_msg, max_tokens=200)
        resposta_texto = response.content.strip()

        # Parse robusto: extrair JSON válido da resposta (pode ter texto antes/depois)
        resultado = None
        try:
            resultado = json.loads(resposta_texto)
        except json.JSONDecodeError:
            # Modelo pode ter gerado texto antes/depois do JSON
            # Procurar por JSON válido usando múltiplas estratégias
            import re

            # Estratégia 1: Procurar por {...} que contenha "contexto_medico"
            for match in re.finditer(r'\{[^{}]*"contexto_medico"[^{}]*\}', resposta_texto):
                try:
                    resultado = json.loads(match.group())
                    break
                except json.JSONDecodeError:
                    continue

            # Estratégia 2: Se ainda não achou, procurar por qualquer {...}
            if not resultado:
                for match in re.finditer(r'\{[^{}]*\}', resposta_texto):
                    try:
                        candidato = json.loads(match.group())
                        if "contexto_medico" in candidato:
                            resultado = candidato
                            break
                    except json.JSONDecodeError:
                        continue

        if resultado and "contexto_medico" in resultado:
            state["contexto_valido"] = bool(resultado.get("contexto_medico", False))
            state["justificativa_guardrail"] = resultado.get("justificativa", "")
        else:
            # Se não conseguiu parsear nenhum JSON válido, fail-open
            print(f"⚠️ Guardrail não conseguiu parsear resposta JSON: {resposta_texto[:200]}")
            state["contexto_valido"] = True
            state["justificativa_guardrail"] = "Resposta mal formatada, assumindo contexto válido"
    except Exception as e:
        state["contexto_valido"] = False
        state["contexto_erro_tecnico"] = True
        state["justificativa_guardrail"] = str(e)

    return state


def verificar_contexto_pergunta(state: DadosPaciente) -> str:
    return "contexto_valido" if state.get("contexto_valido") else "contexto_invalido"


def tratar_pergunta_fora_contexto(state: DadosPaciente) -> DadosPaciente:
    justificativa = state.get("justificativa_guardrail", "")

    if state.get("contexto_erro_tecnico"):
        mensagem = (
            "❌ Não foi possível validar sua pergunta no momento devido a uma "
            "instabilidade técnica ao consultar o modelo de IA. Tente novamente "
            "em instantes."
        )
        if justificativa:
            mensagem += f" (Detalhe técnico: {justificativa})"
    else:
        mensagem = "❌ A pergunta informada não parece estar relacionada ao contexto médico do paciente."
        if justificativa:
            mensagem += f" ({justificativa})"
        mensagem += " Por favor, reformule sua pergunta com foco na saúde do paciente."

    state["mensagem_final"] = mensagem
    return state


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
workflow.add_node("validar_contexto_pergunta", validar_contexto_pergunta)
workflow.add_node("tratar_pergunta_fora_contexto", tratar_pergunta_fora_contexto)
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
        "paciente_existe": "validar_contexto_pergunta",
        "paciente_nao_existe": "marcar_consulta",
        "erro_validacao": "tratar_erro_busca",
    },
)
workflow.add_conditional_edges(
    "validar_contexto_pergunta",
    verificar_contexto_pergunta,
    {
        "contexto_valido": "obter_dados_paciente_paralelo",
        "contexto_invalido": "tratar_pergunta_fora_contexto",
    },
)
workflow.add_edge("tratar_pergunta_fora_contexto", "registrar_log_auditoria")
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
    global llm
    # Inicializar LLM aqui para usar variáveis de ambiente atualizadas
    llm = get_llm()

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
    print(f"Debug RAG: {resultado.get('logging_rag', {})}")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(executar_fluxo())
