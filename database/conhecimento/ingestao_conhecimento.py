"""Ingestão de documentos de conhecimento no vector store (PGVector).

Diferente do ``embeddings_ingest.py`` que ingere atendimentos do banco relacional,
este script ingere **documentos de conhecimento contextual** (protocolos, casos de
estudo, diretrizes, referências, PDFs, planilhas) destinados a enriquecer as
respostas da LLM e garantir rastreabilidade de fontes.

Fluxo:
    fonte documental (PDF/Excel ou exemplo embutido)
        -> LangChain Document Loader
        -> Document
        -> chunking
        -> embeddings
        -> PGVector (coleção de conhecimento)

A ingestão é **idempotente**: cada chunk recebe um ``chunk_id`` estável derivado
do arquivo + página/sheet + hash do conteúdo. Reprocessar o mesmo documento não
gera duplicatas (chunks já presentes são pulados).

Uso:
    python database/conhecimento/ingestao_conhecimento.py --provider mock
    python database/conhecimento/ingestao_conhecimento.py --provider openai --knowledge-dir knowledge
    python database/conhecimento/ingestao_conhecimento.py --provider mock --knowledge-dir knowledge --reset-colecao
"""

import argparse
import os
import sys
import time
from pathlib import Path

RAIZ_PROJETO = Path(__file__).resolve().parents[2]
if str(RAIZ_PROJETO) not in sys.path:
    sys.path.insert(0, str(RAIZ_PROJETO))

from langchain_core.documents import Document

from src.db.connection import conectar, resolver_dsn
from src.db.embeddings import (
    dimensoes_do,
    dividir_documento,
    nome_modelo_do,
    obter_provedor,
)
from src.db.vectorstore import (
    apagar_colecao,
    colecao_conhecimento_para,
    obter_vectorstore_conhecimento,
)

from database.conhecimento.documentos_exemplo import obter_documentos_exemplo
from database.conhecimento.loaders import (
    carregar_diretorio,
    gerar_chunk_id,
)


def _ids_existentes(dsn: str, colecao: str, ids: list[str]) -> set[str]:
    """Consulta a tabela gerenciada pelo PGVector para ids já presentes.

    Retorna o subconjunto de ``ids`` que já existem na coleção (custom_id),
    permitindo uma ingestão idempotente sem duplicar chunks.
    """
    if not ids:
        return set()
    existentes: set[str] = set()
    with conectar(dsn) as con:
        # batch: consulta em blocos de 500 ids
        for inicio in range(0, len(ids), 500):
            bloco = ids[inicio : inicio + 500]
            linhas = con.execute(
                """
                SELECT e.custom_id
                FROM langchain_pg_embedding e
                JOIN langchain_pg_collection c ON c.uuid = e.collection_id
                WHERE c.name = %(colecao)s AND e.custom_id = ANY(%(ids)s)
                """,
                {"colecao": colecao, "ids": bloco},
            ).fetchall()
            existentes.update(linha["custom_id"] for linha in linhas)
    return existentes


def _carregar_documentos_fonte(knowledge_dir: str | None) -> list[Document]:
    """Carrega os documentos-fonte a ingerir.

    - Se ``knowledge_dir`` for informado, carrega os arquivos reais (PDF/Excel)
      do diretório via LangChain Document Loaders.
    - Caso contrário, retorna os documentos de exemplo embutidos (compatibilidade).

    Em ambos os casos retorna documentos já carregados (na forma de Document).
    """
    if knowledge_dir:
        diretorio = Path(knowledge_dir)
        if not diretorio.is_dir():
            raise ValueError(
                f"Diretório de conhecimento não encontrado: {knowledge_dir}"
            )
        docs = carregar_diretorio(diretorio)
        if not docs:
            print(
                f"[conhecimento] nenhum documento suportado encontrado em "
                f"{knowledge_dir} (PDF/Excel)."
            )
        return docs
    return obter_documentos_exemplo()


def rodar_ingestao_conhecimento(
    provedor_nome: str,
    dsn: str | None = None,
    tamanho_lote: int = 64,
    max_chars_chunk: int = 800,
    reset_colecao: bool = False,
    knowledge_dir: str | None = None,
) -> dict:
    provedor = obter_provedor(provedor_nome)
    dsn_resolvido = resolver_dsn(dsn)

    modelo = nome_modelo_do(provedor)
    dimensoes = dimensoes_do(provedor)
    colecao = colecao_conhecimento_para(provedor)

    if reset_colecao:
        print(f"[conhecimento] removendo coleção {colecao} (--reset)...")
        apagar_colecao(provedor, dsn=dsn_resolvido, nome_colecao="assistente_medico_conhecimento")

    vectorstore = obter_vectorstore_conhecimento(provedor, dsn=dsn_resolvido)
    print(f"[conhecimento] provedor={modelo} dim={dimensoes} coleção={colecao}")

    documentos_brutos = _carregar_documentos_fonte(knowledge_dir)
    if not documentos_brutos:
        print("[conhecimento] nada a fazer: nenhum documento-fonte.")
        return {"documentos_fonte": 0, "chunks": 0, "chunks_novos": 0, "chunks_pulados": 0}

    origem = knowledge_dir or "exemplos-embutidos"
    print(f"[conhecimento] {len(documentos_brutos)} documentos-carregados de '{origem}'")

    inicio = time.perf_counter()
    todos_chunks: list[Document] = []
    ids: list[str] = []
    for doc in documentos_brutos:
        chunks = dividir_documento(doc, max_chars_chunk)
        for ordem, chunk in enumerate(chunks):
            todo_id = gerar_chunk_id(chunk, ordem)
            chunk.metadata["chunk_id"] = todo_id
            todos_chunks.append(chunk)
            ids.append(todo_id)

    # Idempotência: apenas chunks ainda não presentes são inseridos
    ja_existentes = _ids_existentes(dsn_resolvido, colecao, ids)
    novos_em_blocos: list[tuple[Document, str]] = [
        (chunk, chunk_id)
        for chunk, chunk_id in zip(todos_chunks, ids)
        if chunk_id not in ja_existentes
    ]
    pulados = len(todos_chunks) - len(novos_em_blocos)

    inseridos = 0
    for inicio_bloco in range(0, len(novos_em_blocos), tamanho_lote):
        bloco = novos_em_blocos[inicio_bloco : inicio_bloco + tamanho_lote]
        docs_bloco = [chunk for chunk, _ in bloco]
        ids_bloco = [chunk_id for _, chunk_id in bloco]
        vectorstore.add_documents(docs_bloco, ids=ids_bloco)
        inseridos += len(docs_bloco)
        print(
            f"[conhecimento] {inseridos}/{len(novos_em_blocos)} novos chunks inseridos"
        )

    elapsed = time.perf_counter() - inicio
    resumo = {
        "documentos_fonte": len(documentos_brutos),
        "chunks": len(todos_chunks),
        "chunks_novos": inseridos,
        "chunks_pulados": pulados,
        "modelo": modelo,
        "dimensoes": dimensoes,
        "origem": origem,
        "segundos": round(elapsed, 1),
    }
    print(
        f"=== Ingestão de conhecimento concluída ===\n"
        f"origem:          {origem}\n"
        f"documentos fonte: {resumo['documentos_fonte']}\n"
        f"chunks gerados:  {resumo['chunks']}\n"
        f"chunks novos:    {resumo['chunks_novos']}\n"
        f"chunks pulados:  {resumo['chunks_pulados']}\n"
        f"duração: {resumo['segundos']}s"
    )
    return resumo


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ingere documentos de conhecimento no vector store (PGVector)."
    )
    parser.add_argument("--provider", default="mock", choices=["mock", "openai"])
    parser.add_argument("--dsn", type=str, default=None, help="DSN do PostgreSQL.")
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--max-chars-chunk", type=int, default=800)
    parser.add_argument(
        "--knowledge-dir",
        type=str,
        default=None,
        help="Diretório com documentos (PDF/Excel). Padrão: env MEDPT_KNOWLEDGE_DIR "
             "ou, se ausente, usa os exemplos embutidos.",
    )
    parser.add_argument(
        "--reset-colecao",
        action="store_true",
        help="Apaga os vetores da coleção antes de ingerir.",
    )
    args = parser.parse_args()

    knowledge_dir = args.knowledge_dir or os.getenv("MEDPT_KNOWLEDGE_DIR") or None

    rodar_ingestao_conhecimento(
        provedor_nome=args.provider,
        dsn=args.dsn,
        tamanho_lote=args.batch_size,
        max_chars_chunk=args.max_chars_chunk,
        reset_colecao=args.reset_colecao,
        knowledge_dir=knowledge_dir,
    )


if __name__ == "__main__":
    main()
