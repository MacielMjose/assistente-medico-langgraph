import numpy as np

from src.db.connection import sessao
from src.db.models import ResultadoVetorial

SQL_CARREGAR = """
    SELECT
        c.atendimento_id,
        c.ordem_chunk,
        c.conteudo,
        c.embedding,
        a.paciente_id,
        a.data_atendimento,
        cond.nome AS condicao,
        e.nome    AS especialidade_principal
    FROM prontuario_chunks c
    JOIN atendimentos a ON a.id = c.atendimento_id
    JOIN condicoes cond ON cond.id = a.condicao_id
    JOIN profissionais pr ON pr.id = a.profissional_id
    JOIN especialidades e ON e.id = pr.especialidade_principal_id
    WHERE c.modelo_embedding = ?
      AND (? IS NULL OR cond.nome = ?)
      AND (? IS NULL OR e.nome = ?)
"""


def _carregar_vetores(conexao, provedor, condicao: str | None, especialidade: str | None):
    linhas = conexao.execute(
        SQL_CARREGAR,
        (provedor.nome_modelo, condicao, condicao, especialidade, especialidade),
    ).fetchall()
    if not linhas:
        return [], np.empty((0, 0), dtype=np.float32)
    matriz = np.vstack([np.frombuffer(linha["embedding"], dtype="<f4") for linha in linhas])
    metadados = [
        {
            "atendimento_id": linha["atendimento_id"],
            "ordem_chunk": linha["ordem_chunk"],
            "conteudo": linha["conteudo"],
            "paciente_id": linha["paciente_id"],
            "data_atendimento": linha["data_atendimento"],
            "condicao": linha["condicao"],
            "especialidade_principal": linha["especialidade_principal"],
        }
        for linha in linhas
    ]
    return metadados, matriz


def buscar_vetorial(
    consulta: str,
    provedor,
    caminho_db=None,
    k: int = 5,
    condicao: str | None = None,
    especialidade: str | None = None,
) -> list[ResultadoVetorial]:
    with sessao(caminho_db) as con:
        metadados, matriz = _carregar_vetores(con, provedor, condicao, especialidade)
    if not metadados:
        return []

    vetor_consulta = np.asarray(provedor.embed_consulta(consulta), dtype=np.float32)
    normas_matriz = np.linalg.norm(matriz, axis=1)
    norma_consulta = np.linalg.norm(vetor_consulta) or 1.0
    normas_matriz[normas_matriz == 0] = 1.0
    similaridades = (matriz @ vetor_consulta) / (normas_matriz * norma_consulta)

    ordem = np.argsort(-similaridades)[:k]
    resultados = []
    for indice in ordem:
        meta = metadados[int(indice)]
        resultados.append(
            ResultadoVetorial(
                **meta,
                similaridade=round(float(similaridades[indice]), 4),
            )
        )
    return resultados


def estatisticas_chunks(caminho_db=None) -> dict:
    with sessao(caminho_db) as con:
        linha = con.execute(
            """
            SELECT COUNT(*) AS total, COALESCE(SUM(dimensoes), 0) AS dim_soma
            FROM prontuario_chunks
            """
        ).fetchone()
        modelos = con.execute(
            "SELECT modelo_embedding, COUNT(*) FROM prontuario_chunks GROUP BY modelo_embedding"
        ).fetchall()
    return {
        "chunks": linha["total"],
        "por_modelo": {m["modelo_embedding"]: m[1] for m in modelos},
    }
