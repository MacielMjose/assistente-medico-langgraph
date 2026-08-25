from src.assistente_medico.graph import build_graph

app = build_graph()

print("Estrutura do grafo:")
print(app.get_graph().draw_ascii())

entrada = {"nome": "José"}
resultado = app.invoke(entrada)

print("Mensagem:", resultado.get("mensagem_final", "<sem retorno>"))
