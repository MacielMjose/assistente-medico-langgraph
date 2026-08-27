"""Ingestão de embeddings via LangChain (PGVector) no PostgreSQL.

Uso:
    python database/embeddings_ingest.py --provider mock --limite 2000
    python database/embeddings_ingest.py --provider openai --limite 50000

Retomável: atendimentos já vetorizados na coleção do provedor são pulados.
Os vetores ficam nas tabelas gerenciadas pelo vector store do LangChain
(langchain_pg_collection / langchain_pg_embedding) — não há mais chunks manuais.
"""

import argparse
import sys
import time
from pathlib import Path

RAIZ_PROJETO = Path(__file__).resolve().parents[1]
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
from src.db.vectorstore import apagar_colecao, colecao_para, estatisticas_chunks, obter_vectorstore

SQL_PENDENTES = """
    SELECT a.id, a.paciente_id, a.data_atendimento, a.queixa, a.conduta,
           c.nome AS condicao,
           e.nome AS especialidade_principal
    FROM atendimentos a
    JOIN condicoes c ON c.id = a.condicao_id
    JOIN profissionais pr ON pr.id = a.profissional_id
    JOIN especialidades e ON e.id = pr.especialidade_principal_id
    LEFT JOIN langchain_pg_embedding emb
           ON emb.collection_id = (SELECT uuid FROM langchain_pg_collection WHERE name = %(colecao)s)
          AND (emb.cmetadata->>'atendimento_id')::BIGINT = a.id
    WHERE emb.uuid IS NULL
    ORDER BY a.id
    LIMIT %(limite)s
"""


def rodar_ingestao(
    provedor_nome: str,
    dsn: str | None = None,
    limite: int = 50_000,
    tamanho_lote: int = 256,
    max_chars_chunk: int = 600,
    reset_colecao: bool = False,
) -> dict:
    provedor = obter_provedor(provedor_nome)
    dsn_resolvido = resolver_dsn(dsn)

    modelo = nome_modelo_do(provedor)
    dimensoes = dimensoes_do(provedor)

    if reset_colecao:
        print(f"[ingest] removendo coleção {colecao_para(provedor)} (--reset)...")
        apagar_colecao(provedor, dsn=dsn_resolvido)

    # Construído depois do reset: o __post_init__ do PGVector recria a coleção.
    vectorstore = obter_vectorstore(provedor, dsn=dsn_resolvido)
    colecao = colecao_para(provedor)
    print(f"[ingest] provedor={modelo} dim={dimensoes} coleção={colecao} limite={limite:,}".replace(",", "."))

    with conectar(dsn_resolvido) as con:
        pendentes = con.execute(
            SQL_PENDENTES, {"colecao": colecao, "limite": limite}
        ).fetchall()
    total_atendimentos = len(pendentes)
    if not pendentes:
        print("[ingest] nada a fazer: nenhum atendimento pendente na coleção.")
        return {"atendimentos": 0, "chunks": 0}

    inicio = time.perf_counter()
    inseridos = 0
    for inicio_bloco in range(0, total_atendimentos, tamanho_lote):
        bloco = pendentes[inicio_bloco : inicio_bloco + tamanho_lote]
        documentos = []
        for linha in bloco:
            documento = Document(
                page_content=f"{linha['queixa']}\n{linha['conduta']}",
                metadata={
                    "atendimento_id": linha["id"],
                    "paciente_id": linha["paciente_id"],
                    "condicao": linha["condicao"],
                    "especialidade_principal": linha["especialidade_principal"],
                    "data_atendimento": linha["data_atendimento"].isoformat(),
                    "modelo": modelo,
                },
            )
            documentos.extend(dividir_documento(documento, max_chars_chunk))
        ids = [
            f"{pedaco.metadata['atendimento_id']}-{pedaco.metadata['ordem_chunk']}"
            for pedaco in documentos
        ]

        vectorstore.add_documents(documentos, ids=ids)
        inseridos += len(documentos)

        processados = min(inicio_bloco + tamanho_lote, total_atendimentos)
        ritmo = inseridos / max(time.perf_counter() - inicio, 1e-6)
        print(
            f"[ingest] {processados:,}/{total_atendimentos:,} atendimentos | "
            f"{inseridos:,} chunks | {ritmo:.0f} chunks/s".replace(",", ".")
        )

    total_geral = estatisticas_chunks(dsn_resolvido)["chunks"]
    resumo = {
        "atendimentos": total_atendimentos,
        "chunks": inseridos,
        "total_na_tabela": total_geral,
        "modelo": modelo,
        "dimensoes": dimensoes,
        "segundos": round(time.perf_counter() - inicio, 1),
    }
    print(
        f"=== Ingestão concluída ===\n"
        f"atendimentos novos: {resumo['atendimentos']:>8}\n"
        f"chunks inseridos:   {resumo['chunks']:>8}\n"
        f"total nas coleções: {resumo['total_na_tabela']:>8}\n"
        f"duração: {resumo['segundos']}s"
    )
    return resumo


def main() -> None:
    parser = argparse.ArgumentParser(description="Gera embeddings dos prontuários (LangChain/PGVector).")
    parser.add_argument("--provider", default="mock", choices=["mock", "openai"])
    parser.add_argument("--dsn", type=str, default=None, help="Usa o DSN informado (ou MEDPT_PG_DSN).")
    parser.add_argument("--limite", type=int, default=50_000)
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--max-chars-chunk", type=int, default=600)
    parser.add_argument(
        "--reset-colecao",
        action="store_true",
        help="Apaga os vetores da coleção do provedor antes de ingerir (útil ao trocar de modelo/provedor).",
    )
    argumentos = parser.parse_args()
    rodar_ingestao(
        provedor_nome=argumentos.provider,
        dsn=argumentos.dsn,
        limite=argumentos.limite,
        tamanho_lote=argumentos.batch_size,
        max_chars_chunk=argumentos.max_chars_chunk,
        reset_colecao=argumentos.reset_colecao,
    )


if __name__ == "__main__":
    main()