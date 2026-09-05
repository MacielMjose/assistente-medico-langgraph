"""Integração do vector store com LangChain (PGVector).

O LangChain gerencia internamente as tabelas `langchain_pg_collection` e
`langchain_pg_embedding` (PostgreSQL + extensão pgvector), substituindo a
antiga tabela manual `prontuario_chunks`. Metadados (atendimento_id, condição,
especialidade, etc.) são persistidos em JSONB e usados como filtros na busca.

A coleção é nomeada por modelo (`assistente_medico_<modelo>`) — assim vetores
de provedores diferentes (mock vs openai) nunca se misturam.
"""

import os
import re
import warnings
from typing import Callable

from langchain_core.embeddings import Embeddings
from langchain_community.vectorstores import PGVector as PGVectorLangChain

warnings.filterwarnings(
    "ignore",
    message=".*langchain-community.*is being sunset.*",
    category=DeprecationWarning,
)

from src.db.connection import resolver_dsn
from src.db.embeddings import nome_modelo_do, obter_provedor

COLECAO_BASE = "assistente_medico"
COLECAO_CONHECIMENTO = "assistente_medico_conhecimento"


def _dsn_sqlalchemy(dsn: str) -> str:
    if dsn.startswith("postgresql://") and "+" not in dsn.split("://")[0]:
        return dsn.replace("postgresql://", "postgresql+psycopg://", 1)
    return dsn


def colecao_para(provedor: Embeddings, nome_colecao: str = COLECAO_BASE) -> str:
    modelo = re.sub(r"[^a-zA-Z0-9_-]", "_", nome_modelo_do(provedor))
    return f"{nome_colecao}_{modelo}"


def colecao_conhecimento_para(provedor: Embeddings) -> str:
    return colecao_para(provedor, COLECAO_CONHECIMENTO)


def obter_vectorstore(
    provedor: Embeddings | None = None,
    dsn: str | None = None,
    nome_colecao: str = COLECAO_BASE,
    embed_documents: Callable | None = None,
) -> PGVectorLangChain:
    """Retorna um PGVector do LangChain criando coleção/tabelas se preciso.

    Argumentos:
        provedor: instância de Embeddings (padrão: provider de MEDPT_EMBEDDING_PROVIDER).
        dsn: conexão (padrão: MEDPT_PG_DSN/DSN_PADRAO).
        nome_colecao: prefixo da coleção; o modelo é anexado ao final.
    """

    if provedor is None:
        provedor = obter_provedor(os.getenv("MEDPT_EMBEDDING_PROVIDER", "mock"))
    return PGVectorLangChain(
        connection_string=_dsn_sqlalchemy(resolver_dsn(dsn)),
        embedding_function=provedor,
        collection_name=colecao_para(provedor, nome_colecao),
        distance_strategy="cosine",
        use_jsonb=True,
    )


def obter_vectorstore_conhecimento(
    provedor: Embeddings | None = None,
    dsn: str | None = None,
) -> PGVectorLangChain:
    """Retorna um PGVector para a coleção de conhecimento contextual.

    A coleção de conhecimento é separada da coleção de atendimentos para
    manter a distinção entre dados estruturados vetORIZADOS e documentos
    de conhecimento que enriquecem as respostas da LLM.
    """
    return obter_vectorstore(
        provedor=provedor,
        dsn=dsn,
        nome_colecao=COLECAO_CONHECIMENTO,
    )


def apagar_colecao(
    provedor: Embeddings | None = None,
    dsn: str | None = None,
    nome_colecao: str = COLECAO_BASE,
) -> None:
    """Remove apenas a coleção do provedor (os vetores), mantendo as demais.

    Usa o método oficial ``PGVector.delete_collection``; coleções inexistentes
    são ignoradas com um aviso registrado pelo próprio LangChain.
    """

    obter_vectorstore(provedor, dsn=dsn, nome_colecao=nome_colecao).delete_collection()


def estatisticas_chunks(dsn: str | None = None, nome_colecao: str = COLECAO_BASE) -> dict:
    """Total de vetores por modelo dentro das coleções do projeto.

    Consulta direta (read-only) nas tabelas criadas pelo LangChain.
    """

    from src.db.connection import conectar

    total = 0
    por_modelo: dict[str, int] = {}
    with conectar(dsn) as con:
        linhas = con.execute(
            """
            SELECT c.name AS colecao, e.cmetadata->>'modelo' AS modelo, COUNT(*) AS total
            FROM langchain_pg_embedding e
            JOIN langchain_pg_collection c ON c.uuid = e.collection_id
            WHERE c.name LIKE %(prefixo)s
            GROUP BY c.name, e.cmetadata->>'modelo'
            ORDER BY c.name
            """,
            {"prefixo": f"{nome_colecao}_%"},
        ).fetchall()
    for linha in linhas:
        por_modelo[f"{linha['colecao']} ({linha['modelo']})"] = linha["total"]
        total += linha["total"]
    return {"chunks": total, "por_modelo": por_modelo}