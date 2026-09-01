"""Testes unitários para os nodes e regras de negócio do fluxo LangGraph em main.py.

Cobre exclusivamente lógica local (validações, condicionais de roteamento,
montagem de estado, tratamento de exceções). Nenhuma chamada real a LLM,
banco de dados ou provedor de embeddings é feita — tudo é mockado via
``monkeypatch`` nos objetos módulo-level de ``main`` (llm, *_repo, obter_provedor).
"""

from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock
import main
import pytest




# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

def _resposta_llm(texto: str) -> SimpleNamespace:
    """Simula o objeto de resposta retornado por ``llm.invoke``."""
    return SimpleNamespace(content=texto)


def _paciente(id_=1, nome="Maria Silva", cpf_mascarado="***.123.456-**"):
    return SimpleNamespace(id=id_, nome=nome, cpf_mascarado=cpf_mascarado)


def _atendimento(id_=1, dias_atras=5, queixa="Dor de cabeça", conduta="Repouso"):
    return SimpleNamespace(
        id=id_,
        data_atendimento=datetime.now() - timedelta(days=dias_atras),
        queixa=queixa,
        conduta=conduta,
    )


def _exame(id_=1, dias_atras=3, nome="Hemograma", resultado="Normal"):
    return SimpleNamespace(
        exame_id=id_,
        nome_exame=nome,
        data_exame=(datetime.now() - timedelta(days=dias_atras)).date(),
        resultado=resultado,
    )


def _condicao(nome="Hipertensão"):
    return SimpleNamespace(condicao=nome)


@pytest.fixture
def mock_llm(monkeypatch):
    """Substitui ``main.llm`` por um MagicMock controlável em cada teste."""
    fake = MagicMock()
    monkeypatch.setattr(main, "llm", fake)
    return fake


# ---------------------------------------------------------------------------
# obter_entrada
# ---------------------------------------------------------------------------

class TestObterEntrada:
    def test_nao_pede_input_quando_nome_e_cpf_ja_presentes(self, monkeypatch):
        chamou_input = MagicMock(side_effect=AssertionError("input() não deveria ser chamado"))
        monkeypatch.setattr("builtins.input", chamou_input)

        estado = main.obter_entrada({"nome": "João", "cpf": "12345678900"})

        assert estado["nome"] == "João"
        assert estado["cpf"] == "12345678900"

    def test_pede_input_quando_nome_ausente(self, monkeypatch):
        respostas = iter(["Ana Souza", "98765432100"])
        monkeypatch.setattr("builtins.input", lambda *_: next(respostas))

        estado = main.obter_entrada({})

        assert estado["nome"] == "Ana Souza"
        assert estado["cpf"] == "98765432100"

    def test_inicializa_campos_padrao_do_estado(self, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda *_: "x")

        estado = main.obter_entrada({"nome": "João", "cpf": "12345678900"})

        assert estado["ja_existe"] is False
        assert estado["paciente"] is None
        assert estado["exames"] is None
        assert estado["data_ultima_consulta"] is None
        assert estado["prontuarios"] is None
        assert estado["tratamento_necessario"] is False
        assert estado["mensagem_final"] == ""


# ---------------------------------------------------------------------------
# validar_dados_paciente
# ---------------------------------------------------------------------------

class TestValidarDadosPaciente:
    def test_dados_validos_sao_normalizados(self):
        estado = main.validar_dados_paciente({"nome": "  João Silva  ", "cpf": "  12345678900  "})

        assert estado["nome"] == "João Silva"
        assert estado["cpf"] == "12345678900"

    def test_nome_vazio_gera_erro(self):
        with pytest.raises(ValueError, match="Nome inválido"):
            main.validar_dados_paciente({"nome": "", "cpf": "12345678900"})

    def test_nome_com_um_caractere_gera_erro(self):
        with pytest.raises(ValueError, match="Nome inválido"):
            main.validar_dados_paciente({"nome": "A", "cpf": "12345678900"})

    def test_cpf_curto_gera_erro(self):
        with pytest.raises(ValueError, match="CPF inválido"):
            main.validar_dados_paciente({"nome": "João Silva", "cpf": "123"})

    def test_cpf_ausente_e_permitido(self):
        estado = main.validar_dados_paciente({"nome": "João Silva", "cpf": None})

        assert estado["cpf"] is None


# ---------------------------------------------------------------------------
# buscar_paciente
# ---------------------------------------------------------------------------

class TestBuscarPaciente:
    def test_sem_nome_ou_cpf_retorna_erro(self, monkeypatch):
        estado = main.buscar_paciente({"nome": "", "cpf": ""})

        assert estado["paciente"] is None
        assert estado["ja_existe"] is False
        assert "obrigatórios" in estado["erro_busca"]

    def test_paciente_nao_encontrado(self, monkeypatch):
        monkeypatch.setattr(main.paciente_repo, "buscar_paciente", MagicMock(return_value=[]))

        estado = main.buscar_paciente({"nome": "Ninguem", "cpf": "12345678900"})

        assert estado["paciente"] is None
        assert estado["ja_existe"] is False
        assert estado["erro_busca"] is None

    def test_paciente_encontrado_sem_cpf_registrado(self, monkeypatch):
        paciente = _paciente(cpf_mascarado="")
        monkeypatch.setattr(main.paciente_repo, "buscar_paciente", MagicMock(return_value=[paciente]))

        estado = main.buscar_paciente({"nome": "Maria Silva", "cpf": "12345678900"})

        assert estado["paciente"] is None
        assert estado["ja_existe"] is False
        assert "não possui CPF registrado" in estado["erro_busca"]

    def test_cpf_divergente_retorna_erro(self, monkeypatch):
        paciente = _paciente(cpf_mascarado="***.999.999-**")
        monkeypatch.setattr(main.paciente_repo, "buscar_paciente", MagicMock(return_value=[paciente]))

        estado = main.buscar_paciente({"nome": "Maria Silva", "cpf": "***.123.456-**"})

        assert estado["paciente"] is None
        assert estado["ja_existe"] is False
        assert "Dados inconsistentes" in estado["erro_busca"]

    def test_paciente_encontrado_com_cpf_correspondente(self, monkeypatch):
        paciente = _paciente(cpf_mascarado="***.123.456-**")
        monkeypatch.setattr(main.paciente_repo, "buscar_paciente", MagicMock(return_value=[paciente]))

        estado = main.buscar_paciente({"nome": "Maria Silva", "cpf": "***.123.456-**"})

        assert estado["paciente"] is paciente
        assert estado["ja_existe"] is True
        assert estado["erro_busca"] is None

    def test_excecao_no_repositorio_e_capturada(self, monkeypatch):
        monkeypatch.setattr(
            main.paciente_repo,
            "buscar_paciente",
            MagicMock(side_effect=RuntimeError("conexão perdida")),
        )

        estado = main.buscar_paciente({"nome": "Maria Silva", "cpf": "12345678900"})

        assert estado["paciente"] is None
        assert estado["ja_existe"] is False
        assert "conexão perdida" in estado["erro_busca"]


# ---------------------------------------------------------------------------
# verificar_paciente_existe / verificar_tratamento_necessario (arestas condicionais)
# ---------------------------------------------------------------------------

class TestArestasCondicionais:
    def test_verificar_paciente_existe_com_erro_de_busca(self):
        assert main.verificar_paciente_existe({"erro_busca": "algum erro"}) == "erro_validacao"

    def test_verificar_paciente_existe_quando_ja_existe(self):
        assert main.verificar_paciente_existe({"erro_busca": None, "ja_existe": True}) == "paciente_existe"

    def test_verificar_paciente_existe_quando_nao_existe(self):
        assert main.verificar_paciente_existe({"erro_busca": None, "ja_existe": False}) == "paciente_nao_existe"

    def test_verificar_tratamento_necessario_true(self):
        assert main.verificar_tratamento_necessario({"tratamento_necessario": True}) == "tratamento_necessario"

    def test_verificar_tratamento_necessario_false(self):
        assert (
            main.verificar_tratamento_necessario({"tratamento_necessario": False})
            == "tratamento_nao_necessario"
        )

    def test_verificar_tratamento_necessario_ausente_no_estado(self):
        assert main.verificar_tratamento_necessario({}) == "tratamento_nao_necessario"


# ---------------------------------------------------------------------------
# tratar_erro_busca
# ---------------------------------------------------------------------------

class TestTratarErroBusca:
    def test_com_erro_define_mensagem_final(self):
        estado = main.tratar_erro_busca({"erro_busca": "CPF inválido"})

        assert estado["mensagem_final"] == "❌ ERRO: CPF inválido"

    def test_sem_erro_nao_altera_mensagem(self):
        estado = main.tratar_erro_busca({"erro_busca": None, "mensagem_final": ""})

        assert estado["mensagem_final"] == ""


# ---------------------------------------------------------------------------
# _executar_obter_prontuarios (helper async usado por obter_dados_paciente_paralelo)
# ---------------------------------------------------------------------------

class TestExecutarObterProntuarios:
    def test_sucesso_monta_prontuarios_exames_e_ultima_consulta(self, monkeypatch):
        atendimento = _atendimento(id_=1, dias_atras=2)
        exame = _exame(id_=1, dias_atras=1)
        condicao = _condicao("Diabetes")

        monkeypatch.setattr(
            main.atendimento_repo, "obter_prontuarios", MagicMock(return_value=[atendimento])
        )
        monkeypatch.setattr(
            main.atendimento_repo, "obter_condicoes", MagicMock(return_value=[condicao])
        )
        monkeypatch.setattr(main.atendimento_repo, "obter_exames", MagicMock(return_value=[exame]))

        resultado = asyncio.run(main._executar_obter_prontuarios(1))

        assert len(resultado["prontuarios"]) == 1
        assert resultado["prontuarios"][0]["condicoes"] == ["Diabetes"]
        assert len(resultado["exames"]) == 1
        assert resultado["data_ultima_consulta"] == atendimento.data_atendimento.date()

    def test_sem_atendimentos_data_ultima_consulta_e_none(self, monkeypatch):
        monkeypatch.setattr(main.atendimento_repo, "obter_prontuarios", MagicMock(return_value=[]))
        monkeypatch.setattr(main.atendimento_repo, "obter_condicoes", MagicMock(return_value=[]))
        monkeypatch.setattr(main.atendimento_repo, "obter_exames", MagicMock(return_value=[]))

        resultado = asyncio.run(main._executar_obter_prontuarios(1))

        assert resultado == {"prontuarios": [], "exames": [], "data_ultima_consulta": None}

    def test_excecao_retorna_estrutura_vazia(self, monkeypatch):
        monkeypatch.setattr(
            main.atendimento_repo,
            "obter_prontuarios",
            MagicMock(side_effect=RuntimeError("erro db")),
        )

        resultado = asyncio.run(main._executar_obter_prontuarios(1))

        assert resultado == {"prontuarios": [], "exames": [], "data_ultima_consulta": None}


# ---------------------------------------------------------------------------
# _executar_recuperar_documentos
# ---------------------------------------------------------------------------

class TestExecutarRecuperarDocumentos:
    def test_sem_prontuarios_retorna_lista_vazia(self):
        resultado = asyncio.run(main._executar_recuperar_documentos([]))

        assert resultado == {"documentos_similares": []}

    def test_prontuarios_sem_texto_util_retorna_vazio(self, monkeypatch):
        provedor_mock = MagicMock()
        monkeypatch.setattr(main, "obter_provedor", MagicMock(return_value=provedor_mock))
        monkeypatch.setattr(main.busca_repo, "buscar_vetorial", MagicMock())

        resultado = asyncio.run(main._executar_recuperar_documentos([{"queixa": "", "conduta": ""}]))

        assert resultado == {"documentos_similares": []}
        main.busca_repo.buscar_vetorial.assert_not_called()

    def test_sucesso_retorna_documentos_formatados(self, monkeypatch):
        resultado_busca = SimpleNamespace(
            atendimento_id=10,
            similaridade=0.87,
            conteudo="conteúdo relevante",
            condicao="Asma",
            especialidade_principal="Pneumologia",
            data_atendimento=datetime.now(),
        )
        monkeypatch.setattr(main, "obter_provedor", MagicMock(return_value=MagicMock()))
        monkeypatch.setattr(
            main.busca_repo, "buscar_vetorial", MagicMock(return_value=[resultado_busca])
        )

        resultado = asyncio.run(
            main._executar_recuperar_documentos([{"queixa": "Tosse", "conduta": "Xarope"}])
        )

        assert len(resultado["documentos_similares"]) == 1
        assert resultado["documentos_similares"][0]["condicao"] == "Asma"

    def test_excecao_retorna_lista_vazia(self, monkeypatch):
        monkeypatch.setattr(
            main, "obter_provedor", MagicMock(side_effect=RuntimeError("provedor indisponível"))
        )

        resultado = asyncio.run(
            main._executar_recuperar_documentos([{"queixa": "Tosse", "conduta": "Xarope"}])
        )

        assert resultado == {"documentos_similares": []}


# ---------------------------------------------------------------------------
# obter_dados_paciente_paralelo
# ---------------------------------------------------------------------------

class TestObterDadosPacienteParalelo:
    def test_sem_paciente_zera_campos(self):
        estado = asyncio.run(main.obter_dados_paciente_paralelo({"paciente": None}))

        assert estado["prontuarios"] == []
        assert estado["exames"] == []
        assert estado["documentos_similares"] == []

    def test_com_paciente_encadeia_prontuarios_e_documentos(self, monkeypatch):
        paciente = _paciente(id_=42)

        async def fake_obter_prontuarios(paciente_id):
            assert paciente_id == 42
            return {"prontuarios": [{"queixa": "Febre", "conduta": "Antitérmico"}], "exames": [], "data_ultima_consulta": None}

        async def fake_recuperar_documentos(prontuarios):
            assert prontuarios == [{"queixa": "Febre", "conduta": "Antitérmico"}]
            return {"documentos_similares": [{"condicao": "Gripe"}]}

        monkeypatch.setattr(main, "_executar_obter_prontuarios", fake_obter_prontuarios)
        monkeypatch.setattr(main, "_executar_recuperar_documentos", fake_recuperar_documentos)

        estado = asyncio.run(main.obter_dados_paciente_paralelo({"paciente": paciente}))

        assert estado["prontuarios"] == [{"queixa": "Febre", "conduta": "Antitérmico"}]
        assert estado["documentos_similares"] == [{"condicao": "Gripe"}]


# ---------------------------------------------------------------------------
# consultar_modelo_llm
# ---------------------------------------------------------------------------

class TestConsultarModeloLlm:
    def test_sucesso_armazena_analise(self, mock_llm):
        mock_llm.invoke.return_value = _resposta_llm("Análise clínica detalhada")

        estado = main.consultar_modelo_llm(
            {"nome": "João", "prontuarios": [], "exames": [], "documentos_similares": []}
        )

        assert estado["analise_llm"] == "Análise clínica detalhada"

    def test_excecao_armazena_mensagem_de_erro(self, mock_llm):
        mock_llm.invoke.side_effect = RuntimeError("timeout")

        estado = main.consultar_modelo_llm(
            {"nome": "João", "prontuarios": [], "exames": [], "documentos_similares": []}
        )

        assert "Erro ao consultar LLM" in estado["analise_llm"]
        assert "timeout" in estado["analise_llm"]


# ---------------------------------------------------------------------------
# gerar_explicacao
# ---------------------------------------------------------------------------

class TestGerarExplicacao:
    def test_sucesso_armazena_explicacao(self, mock_llm):
        mock_llm.invoke.return_value = _resposta_llm("Explicação simples para o paciente")

        estado = main.gerar_explicacao({"analise_llm": "análise", "nome": "João"})

        assert estado["explicacao"] == "Explicação simples para o paciente"

    def test_excecao_usa_mensagem_padrao(self, mock_llm):
        mock_llm.invoke.side_effect = RuntimeError("indisponível")

        estado = main.gerar_explicacao({"analise_llm": "análise", "nome": "João"})

        assert estado["explicacao"] == "Não foi possível gerar uma explicação neste momento."


# ---------------------------------------------------------------------------
# extrair_alergias
# ---------------------------------------------------------------------------

class TestExtrairAlergias:
    def test_sem_analise_retorna_lista_vazia(self, mock_llm):
        estado = main.extrair_alergias({"analise_llm": ""})

        assert estado["alergias_extraidas"] == []
        mock_llm.invoke.assert_not_called()

    def test_sucesso_faz_parse_do_json(self, mock_llm):
        mock_llm.invoke.return_value = _resposta_llm(
            '{"alergias": [{"nome": "Penicilina", "tipo": "medicamento", '
            '"severidade": "grave", "reacao": "anafilaxia"}]}'
        )

        estado = main.extrair_alergias({"analise_llm": "paciente alérgico a penicilina"})

        assert estado["alergias_extraidas"] == [
            {
                "nome": "Penicilina",
                "tipo": "medicamento",
                "severidade": "grave",
                "reacao": "anafilaxia",
            }
        ]

    def test_json_invalido_retorna_lista_vazia(self, mock_llm):
        mock_llm.invoke.return_value = _resposta_llm("não é json")

        estado = main.extrair_alergias({"analise_llm": "análise qualquer"})

        assert estado["alergias_extraidas"] == []

    def test_excecao_do_llm_retorna_lista_vazia(self, mock_llm):
        mock_llm.invoke.side_effect = RuntimeError("falha")

        estado = main.extrair_alergias({"analise_llm": "análise qualquer"})

        assert estado["alergias_extraidas"] == []


# ---------------------------------------------------------------------------
# validar_com_profissional
# ---------------------------------------------------------------------------

class TestValidarComProfissional:
    def test_marca_validado_com_comentario(self):
        estado = main.validar_com_profissional({})

        assert estado["validacao_profissional"]["validado"] is True
        assert estado["validacao_profissional"]["comentarios"] == "Análise revisada e aprovada."
        assert "timestamp" in estado["validacao_profissional"]


# ---------------------------------------------------------------------------
# sugerir_tratamentos
# ---------------------------------------------------------------------------

class TestSugerirTratamentos:
    def test_tratamento_necessario_quando_resposta_longa(self, mock_llm):
        mock_llm.invoke.return_value = _resposta_llm("1. Repouso\n2. Hidratação\n3. Retorno em 7 dias")

        estado = main.sugerir_tratamentos({"analise_llm": "análise"})

        assert estado["tratamento_necessario"] is True
        assert "Repouso" in estado["tratamentos"]

    def test_tratamento_nao_necessario_quando_resposta_curta(self, mock_llm):
        mock_llm.invoke.return_value = _resposta_llm("Nenhum")

        estado = main.sugerir_tratamentos({"analise_llm": "análise"})

        assert estado["tratamento_necessario"] is False

    def test_tratamento_nao_necessario_quando_resposta_vazia(self, mock_llm):
        mock_llm.invoke.return_value = _resposta_llm("")

        estado = main.sugerir_tratamentos({"analise_llm": "análise"})

        assert estado["tratamento_necessario"] is False

    def test_excecao_marca_tratamento_nao_necessario(self, mock_llm):
        mock_llm.invoke.side_effect = RuntimeError("falha")

        estado = main.sugerir_tratamentos({"analise_llm": "análise"})

        assert estado["tratamento_necessario"] is False
        assert estado["tratamentos"] == "Não foi possível sugerir tratamentos."


# ---------------------------------------------------------------------------
# validar_alergias_guardrail
# ---------------------------------------------------------------------------

class TestValidarAlergiasGuardrail:
    def test_sem_alergias_mantem_estado_seguro_sem_chamar_llm(self, mock_llm):
        estado = main.validar_alergias_guardrail({"alergias_extraidas": [], "tratamentos": "Amoxicilina"})

        assert estado["validacao_alergias"] == {"conflitos": [], "seguro": True, "avisos": []}
        mock_llm.invoke.assert_not_called()

    def test_sem_tratamentos_mantem_estado_seguro_sem_chamar_llm(self, mock_llm):
        estado = main.validar_alergias_guardrail(
            {"alergias_extraidas": [{"nome": "Penicilina"}], "tratamentos": ""}
        )

        assert estado["validacao_alergias"]["seguro"] is True
        mock_llm.invoke.assert_not_called()

    def test_conflito_bloqueia_tratamento(self, mock_llm):
        mock_llm.invoke.return_value = _resposta_llm(
            '{"conflitos": [{"medicamento": "Amoxicilina", "alergia": "Penicilina", '
            '"risco": "anafilaxia"}], "seguro": false}'
        )

        estado = main.validar_alergias_guardrail(
            {
                "alergias_extraidas": [{"nome": "Penicilina"}],
                "tratamentos": "Tomar Amoxicilina 500mg",
            }
        )

        assert estado["validacao_alergias"]["seguro"] is False
        assert len(estado["validacao_alergias"]["conflitos"]) == 1
        assert estado["tratamento_necessario"] is False
        assert "BLOQUEADOS POR GUARDRAIL" in estado["tratamentos"]
        assert "Amoxicilina" in estado["validacao_alergias"]["avisos"][0]

    def test_sem_conflito_mantem_tratamento_original(self, mock_llm):
        mock_llm.invoke.return_value = _resposta_llm('{"conflitos": [], "seguro": true}')

        estado = main.validar_alergias_guardrail(
            {
                "alergias_extraidas": [{"nome": "Glúten"}],
                "tratamentos": "Tomar Amoxicilina 500mg",
                "tratamento_necessario": True,
            }
        )

        assert estado["validacao_alergias"]["seguro"] is True
        assert estado["tratamento_necessario"] is True
        assert estado["tratamentos"] == "Tomar Amoxicilina 500mg"

    def test_excecao_e_capturada_sem_alterar_estado_padrao(self, mock_llm):
        mock_llm.invoke.side_effect = RuntimeError("falha llm")

        estado = main.validar_alergias_guardrail(
            {
                "alergias_extraidas": [{"nome": "Penicilina"}],
                "tratamentos": "Amoxicilina",
            }
        )

        assert estado["validacao_alergias"] == {"conflitos": [], "seguro": True, "avisos": []}


# ---------------------------------------------------------------------------
# marcar_consulta
# ---------------------------------------------------------------------------

class TestMarcarConsulta:
    def test_sem_paciente_nao_agenda(self):
        estado = main.marcar_consulta({"paciente": None})

        assert estado["agendamento"] is None

    def test_com_paciente_cria_agendamento(self, monkeypatch):
        paciente = _paciente(id_=7)
        monkeypatch.setattr(main.agendamento_repo, "criar_agendamento", MagicMock(return_value=99))

        estado = main.marcar_consulta({"paciente": paciente, "explicacao": "Retornar em 7 dias"})

        assert estado["agendamento"]["id"] == 99
        assert "data" in estado["agendamento"]
        chamada = main.agendamento_repo.criar_agendamento.call_args.args[0]
        assert chamada["paciente_id"] == 7
        assert chamada["observacoes"] == "Retornar em 7 dias"

    def test_excecao_no_repositorio_retorna_none(self, monkeypatch):
        paciente = _paciente(id_=7)
        monkeypatch.setattr(
            main.agendamento_repo,
            "criar_agendamento",
            MagicMock(side_effect=RuntimeError("erro db")),
        )

        estado = main.marcar_consulta({"paciente": paciente})

        assert estado["agendamento"] is None


# ---------------------------------------------------------------------------
# emitir_alertas
# ---------------------------------------------------------------------------

class TestEmitirAlertas:
    def test_sem_dados_nao_gera_alertas(self):
        estado = main.emitir_alertas({"data_ultima_consulta": None, "exames": [], "tratamento_necessario": False})

        assert estado["alertas"] == []

    def test_consulta_antiga_gera_alerta(self):
        data_antiga = (datetime.now() - timedelta(days=200)).date()

        estado = main.emitir_alertas(
            {"data_ultima_consulta": data_antiga, "exames": [], "tratamento_necessario": False}
        )

        assert len(estado["alertas"]) == 1
        assert "sem consulta há" in estado["alertas"][0]

    def test_consulta_recente_nao_gera_alerta_de_ausencia(self):
        data_recente = (datetime.now() - timedelta(days=10)).date()

        estado = main.emitir_alertas(
            {"data_ultima_consulta": data_recente, "exames": [], "tratamento_necessario": False}
        )

        assert estado["alertas"] == []

    def test_tratamento_necessario_gera_alerta(self):
        estado = main.emitir_alertas(
            {"data_ultima_consulta": None, "exames": [], "tratamento_necessario": True}
        )

        assert "acompanhamento profissional" in estado["alertas"][0]

    def test_exame_recente_gera_alerta_com_data(self):
        exame = {"data": "2026-01-01", "nome": "Hemograma"}

        estado = main.emitir_alertas(
            {"data_ultima_consulta": None, "exames": [exame], "tratamento_necessario": False}
        )

        assert "2026-01-01" in estado["alertas"][0]

    def test_todos_os_alertas_combinados(self):
        data_antiga = (datetime.now() - timedelta(days=365)).date()
        exame = {"data": "2026-02-02", "nome": "Raio-X"}

        estado = main.emitir_alertas(
            {"data_ultima_consulta": data_antiga, "exames": [exame], "tratamento_necessario": True}
        )

        assert len(estado["alertas"]) == 3


# ---------------------------------------------------------------------------
# registrar_log_auditoria
# ---------------------------------------------------------------------------

class TestRegistrarLogAuditoria:
    def test_sucesso_grava_log_e_monta_mensagem(self, monkeypatch):
        monkeypatch.setattr(main.log_repo, "registrar_log", MagicMock(return_value=555))

        estado = main.registrar_log_auditoria(
            {
                "nome": "João",
                "ja_existe": True,
                "tratamento_necessario": False,
                "agendamento": {"id": 1, "data": "2026-09-08T10:00:00"},
                "alertas": ["Paciente sem consulta há 200 dias"],
                "mensagem_final": "",
            }
        )

        assert estado["log_id"] == 555
        assert "Analise concluida para João" in estado["mensagem_final"]
        assert "2026-09-08T10:00:00" in estado["mensagem_final"]
        assert "Paciente sem consulta há 200 dias" in estado["mensagem_final"]

    def test_excecao_no_log_nao_impede_mensagem_final(self, monkeypatch):
        monkeypatch.setattr(
            main.log_repo, "registrar_log", MagicMock(side_effect=RuntimeError("erro db"))
        )

        estado = main.registrar_log_auditoria(
            {"nome": "João", "ja_existe": False, "tratamento_necessario": False, "mensagem_final": ""}
        )

        assert estado["log_id"] is None
        assert "Analise concluida para João" in estado["mensagem_final"]

    def test_mensagem_de_erro_existente_e_preservada(self, monkeypatch):
        monkeypatch.setattr(main.log_repo, "registrar_log", MagicMock(return_value=1))

        estado = main.registrar_log_auditoria(
            {
                "nome": "João",
                "ja_existe": False,
                "tratamento_necessario": False,
                "mensagem_final": "❌ ERRO: CPF inválido",
            }
        )

        assert estado["mensagem_final"] == "❌ ERRO: CPF inválido"

    def test_sem_agendamento_nem_alertas_gera_mensagem_simples(self, monkeypatch):
        monkeypatch.setattr(main.log_repo, "registrar_log", MagicMock(return_value=1))

        estado = main.registrar_log_auditoria(
            {"nome": "João", "ja_existe": False, "tratamento_necessario": False, "mensagem_final": ""}
        )

        assert estado["mensagem_final"].strip() == "Analise concluida para João."
