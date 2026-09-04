"""
Script de teste para visualizar o guardrail de alergias em ação.
Executa o fluxo LangGraph e mostra os resultados do guardrail.
"""

import asyncio
import json
import sys
from main import app

# Dados de teste
ENTRADA_TESTE = {
    "nome": "Lara Abreu",
    "cpf": "***.917.803-**",
}


async def executar_teste_guardrail():
    """Executa o fluxo e mostra resultados do guardrail."""

    print("\n" + "=" * 80)
    print("TESTE DO GUARDRAIL DE ALERGIAS")
    print("=" * 80)
    print(f"Paciente: {ENTRADA_TESTE['nome']}")
    print(f"CPF: {ENTRADA_TESTE['cpf']}\n")

    # Executar fluxo
    resultado = await app.ainvoke(ENTRADA_TESTE)

    # Exibir resultados
    print("\n" + "-" * 80)
    print("1️⃣ ALERGIAS EXTRAÍDAS DA ANÁLISE")
    print("-" * 80)
    alergias = resultado.get("alergias_extraidas", [])
    if alergias:
        print(json.dumps(alergias, ensure_ascii=False, indent=2))
    else:
        print("❌ Nenhuma alergia detectada")

    print("\n" + "-" * 80)
    print("2️⃣ TRATAMENTOS SUGERIDOS")
    print("-" * 80)
    tratamentos = resultado.get("tratamentos", "")
    print(tratamentos[:500] + "..." if len(tratamentos) > 500 else tratamentos)

    print("\n" + "-" * 80)
    print("3️⃣ VALIDAÇÃO DE ALERGIAS (GUARDRAIL)")
    print("-" * 80)
    validacao = resultado.get("validacao_alergias", {})

    if validacao:
        print(f"Seguro: {'✅ SIM' if validacao.get('seguro') else '❌ NÃO'}")

        conflitos = validacao.get("conflitos", [])
        if conflitos:
            print(f"\nConflitos encontrados: {len(conflitos)}")
            for i, conflito in enumerate(conflitos, 1):
                print(f"\n  {i}. CONFLITO DETECTADO:")
                print(f"     Medicamento: {conflito['medicamento']}")
                print(f"     Alergia: {conflito['alergia']}")
                print(f"     Risco: {conflito['risco']}")
                print(f"     Tipo: {conflito['tipo']}")
        else:
            print("✅ Nenhum conflito encontrado")

        avisos = validacao.get("avisos", [])
        if avisos:
            print(f"\nAvisos:")
            for aviso in avisos:
                print(f"  {aviso}")

    print("\n" + "-" * 80)
    print("4️⃣ DECISÃO FINAL DO SISTEMA")
    print("-" * 80)
    mensagem_final = resultado.get("mensagem_final", "")
    print(mensagem_final)

    print("\n" + "-" * 80)
    print("5️⃣ LOG DE AUDITORIA")
    print("-" * 80)
    log_id = resultado.get("log_id", "N/A")
    print(f"Log ID: {log_id}")
    print(f"Agendamento: {resultado.get('agendamento', {})}")
    print(f"Alertas: {resultado.get('alertas', [])}")

    print("\n" + "=" * 80)
    print("FIM DO TESTE")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    asyncio.run(executar_teste_guardrail())
