"""Provedores de embeddings via LangChain + divisão em chunks (Document).

Usa Ollama local para embeddings. Configure o modelo em MEDPT_OLLAMA_EMBEDDING_MODEL.

Uso:
    provedor = obter_provedor("ollama")
    chunks = dividir_documento(Document(page_content=...))
"""

import os

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_ollama import OllamaEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

OLLAMA_URL_PADRAO = "http://localhost:11434"

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


def obter_provedor(nome: str) -> Embeddings:
    """Obtém o provedor de embeddings. Suporta 'ollama' e 'mock' (para testes)."""
    escolha = nome.strip().lower()

    if escolha == "ollama":
        modelo = os.getenv("MEDPT_OLLAMA_EMBEDDING_MODEL", "").strip()
        if not modelo:
            raise RuntimeError(
                "MEDPT_OLLAMA_EMBEDDING_MODEL ausente no .env. Configure o modelo "
                "de embedding do Ollama (ex: bge-m3, nomic-embed-text)."
            )
        base_url = os.getenv("MEDPT_OLLAMA_BASE_URL", OLLAMA_URL_PADRAO) or OLLAMA_URL_PADRAO
        return OllamaEmbeddings(model=modelo, base_url=base_url)

    if escolha == "mock":
        from langchain_core.embeddings import DeterministicFakeEmbedding
        return DeterministicFakeEmbedding(size=64)

    raise ValueError(f"Provedor desconhecido: '{nome}'. Use: ollama ou mock.")