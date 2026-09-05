"""Ingestão de documentos de conhecimento no vector store (PGVector).

Diferente do ``embeddings_ingest.py`` que ingere atendimentos do banco relacional,
este script ingere documentos de conhecimento contextual (protocolos, casos de
estudo, diretrizes, referências) destinados a enriquecer as respostas da LLM
e permitir rastreabilidade de fontes.

Uso:
    python database/conhecimento/ingestao_conhecimento.py --provider mock
    python database/conhecimento/ingestao_conhecimento.py --provider openai --reset-colecao
"""

import argparse
import sys
import time
from pathlib import Path

RAIZ_PROJETO = Path(__file__).resolve().parents[2]
if str(RAIZ_PROJETO) not in sys.path:
    sys.path.insert(0, str(RAIZ_PROJETO))

from src.db.connection import resolver_dsn
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


def rodar_ingestao_conhecimento(
    provedor_nome: str,
    dsn: str | None = None,
    tamanho_lote: int = 64,
    max_chars_chunk: int = 800,
    reset_colecao: bool = False,
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

    documentos_brutos = obter_documentos_exemplo()
    print(f"[conhecimento] {len(documentos_brutos)} documentos de conhecimento carregados")

    inicio = time.perf_counter()
    todos_documentos = []
    for doc in documentos_brutos:
        chunks = dividir_documento(doc, max_chars_chunk)
        todos_documentos.extend(chunks)

    ids = [
        f"conhecimento_{idx}_{doc.metadata.get('document_type', 'doc')}_{doc.metadata.get('title', '')[:30]}"
        for idx, doc in enumerate(todos_documentos)
    ]

    inseridos = 0
    for inicio_bloco in range(0, len(todos_documentos), tamanho_lote):
        bloco = todos_documentos[inicio_bloco : inicio_bloco + tamanho_lote]
        bloco_ids = ids[inicio_bloco : inicio_bloco + tamanho_lote]
        vectorstore.add_documents(bloco, ids=bloco_ids)
        inseridos += len(bloco)
        print(
            f"[conhecimento] {inseridos}/{len(todos_documentos)} chunks inseridos"
        )

    elapsed = time.perf_counter() - inicio
    print(
        f"=== Ingestão de conhecimento concluída ===\n"
        f"documentos fonte: {len(documentos_brutos)}\n"
        f"chunks inseridos:  {inseridos}\n"
        f"duração: {elapsed:.1f}s"
    )
    return {
        "documentos_fonte": len(documentos_brutos),
        "chunks": inseridos,
        "modelo": modelo,
        "dimensoes": dimensoes,
        "segundos": round(elapsed, 1),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ingere documentos de conhecimento no vector store (PGVector)."
    )
    parser.add_argument("--provider", default="mock", choices=["mock", "openai"])
    parser.add_argument("--dsn", type=str, default=None, help="DSN do PostgreSQL.")
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--max-chars-chunk", type=int, default=800)
    parser.add_argument(
        "--reset-colecao",
        action="store_true",
        help="Apaga os vetores da coleção antes de ingerir.",
    )
    args = parser.parse_args()
    rodar_ingestao_conhecimento(
        provedor_nome=args.provider,
        dsn=args.dsn,
        tamanho_lote=args.batch_size,
        max_chars_chunk=args.max_chars_chunk,
        reset_colecao=args.reset_colecao,
    )


if __name__ == "__main__":
    main()
