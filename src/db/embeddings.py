"""Provedores de embeddings via LangChain + divisão em chunks (Document).

A integração usa as abstrações oficiais de LangChain:
  * OpenAIEmbeddings (produção) -> text-embedding-3-small
  * DeterministicFakeEmbedding (testes/mock, determinístico pelo conteúdo do texto)
  * RecursiveCharacterTextSplitter + Document (chunking de prontuários)

Uso:
    provedor = obter_provedor("openai")   # ou "mock"
    chunks = dividir_documento(Document(page_content=...))
"""

import os

from langchain_core.documents import Document
from langchain_core.embeddings import DeterministicFakeEmbedding, Embeddings
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

MODELO_OPENAI = "text-embedding-3-small"
DIMS_OPENAI = 1536

MODELO_MOCK = "fake-embeddings"
DIMS_MOCK = 64

TAMANHO_CHUNK = 600
SOBREPOSICAO_CHUNK = 50

SEPARADORES = ["\n\n", "\n", ". ", " ", ""]


def dividir_em_chunks(texto: str, max_chars: int = TAMANHO_CHUNK) -> list[str]:
    """Divide um texto (queixa + conduta) em pedaços de tamanho máximo."""

    return [
        " ".join(chunk.split())
        for chunk in RecursiveCharacterTextSplitter(
            chunk_size=max_chars,
            chunk_overlap=min(SOBREPOSICAO_CHUNK, max_chars // 4),
            separators=SEPARADORES,
        ).split_text(texto)
    ]


def dividir_documento(documento: Document, max_chars: int = TAMANHO_CHUNK) -> list[Document]:
    """Divide um Document em chunk Documents usando o splitter oficial do LangChain.

    Cada pedaço herda os metadados do documento original e ganha
    ``ordem_chunk`` (0-based) para manter a ordem dentro do atendimento.
    """

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=max_chars,
        chunk_overlap=min(SOBREPOSICAO_CHUNK, max_chars // 4),
        separators=SEPARADORES,
    )
    pedacos = []
    for indice, pedaco in enumerate(splitter.split_documents([documento])):
        pedaco.page_content = " ".join(pedaco.page_content.split())
        pedaco.metadata["ordem_chunk"] = indice
        pedacos.append(pedaco)
    return pedacos


def _mock_embeddings() -> DeterministicFakeEmbedding:
    return DeterministicFakeEmbedding(size=DIMS_MOCK)


def _openai_embeddings() -> OpenAIEmbeddings:
    chave = os.getenv("OPENAI_API_KEY")
    if not chave:
        raise RuntimeError(
            "OPENAI_API_KEY ausente. Atenção: a chave da Groq não funciona na API "
            "da OpenAI; cadastre uma chave válida em https://platform.openai.com."
        )
    return OpenAIEmbeddings(model=MODELO_OPENAI, api_key=chave)


def obter_provedor(nome: str) -> Embeddings:
    escolha = nome.strip().lower()
    if escolha == "mock":
        return _mock_embeddings()
    if escolha == "openai":
        return _openai_embeddings()
    raise ValueError(f"Provedor desconhecido: '{nome}'. Use: mock ou openai.")


def nome_modelo_do(provedor: Embeddings) -> str:
    """Rótulo estável para distinguir vetores entre modelos."""

    if isinstance(provedor, OpenAIEmbeddings):
        return provedor.model
    if isinstance(provedor, DeterministicFakeEmbedding):
        return MODELO_MOCK
    return type(provedor).__name__


def dimensoes_do(provedor: Embeddings) -> int:
    """Dimensão do vetor produzido pelo provedor."""

    if isinstance(provedor, OpenAIEmbeddings):
        return DIMS_OPENAI
    if isinstance(provedor, DeterministicFakeEmbedding):
        return provedor.size
    return len(provedor.embed_query("verificação"))