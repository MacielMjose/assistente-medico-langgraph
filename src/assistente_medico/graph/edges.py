from src.assistente_medico.graph.state import DadosPaciente


def verificar_paciente_existe(state: DadosPaciente) -> str:
    return "paciente_existe" if state.get("paciente") else "paciente_nao_existe"


def verificar_tratamento_necessario(state: DadosPaciente) -> str:
    return (
        "tratamento_necessario"
        if state.get("tratamento")
        else "tratamento_nao_necessario"
    )
