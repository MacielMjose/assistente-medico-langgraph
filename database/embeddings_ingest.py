"""Ingestão de embeddings: atendimentos -> prontuario_chunks.

Uso:
    python database/embeddings_ingest.py --provider mock --limite 2000
    python database/embeddings_ingest.py --provider openai --limite 50000
    python database/embeddings_ingest.py --provider local --limite 5000

Retomável: atendimentos que já possuem chunks são pulados automaticamente.
"""

import argparse
import sys
import time
from pathlib import Path

import numpy as np

RAIZ_PROJETO = Path(__file__).resolve().parents[1]
if str(RAIZ_PROJETO) not in sys.path:
    sys.path.insert(0, str(RAIZ_PROJETO))

from src.db.connection import DB_PADRAO, conectar
from src.db.embeddings import dividir_em_chunks, obter_provedor

SQL_PENDENTES = """
    SELECT a.id, a.queixa, a.conduta
    FROM atendimentos a
    LEFT JOIN prontuario_chunks c ON c.atendimento_id = a.id
    WHERE c.id IS NULL
    ORDER BY a.id
    LIMIT ?
"""

SQL_INSERIR_CHUNK = """
    INSERT INTO prontuario_chunks
        (atendimento_id, ordem_chunk, conteudo, embedding, modelo_embedding, dimensoes)
    VALUES (?, ?, ?, ?, ?, ?)
"""


def _vetor_para_blob(vetor: list[float]) -> bytes:
    return np.asarray(vetor, dtype="<f4").tobytes()


def rodar_ingestao(
    provedor_nome: str,
    caminho_db=DB_PADRAO,
    limite: int = 50_000,
    tamanho_lote: int = 256,
    max_chars_chunk: int = 600,
) -> dict:
    provedor = obter_provedor(provedor_nome)
    if provedor_nome.lower() != "mock":
        print(f"[ingest] verificando provedor '{provedor.nome_modelo}' (dim={provedor.dimensoes})...")
        provedor.verificar()
    print(f"[ingest] provedor={provedor.nome_modelo} dim={provedor.dimensoes} limite={limite:,}".replace(",", "."))

    con = conectar(caminho_db)
    pendentes = con.execute(SQL_PENDENTES, (limite,)).fetchall()
    total_atendimentos = len(pendentes)
    if not pendentes:
        print("[ingest] nada a fazer: nenhum atendimento pendente.")
        con.close()
        return {"atendimentos": 0, "chunks": 0}

    inicio = time.perf_counter()
    inseridos = 0
    lote_linhas: list[tuple] = []

    def _descarregar() -> None:
        nonlocal inseridos
        if lote_linhas:
            con.executemany(SQL_INSERIR_CHUNK, lote_linhas)
            inseridos += len(lote_linhas)
            lote_linhas.clear()

    for inicio_bloco in range(0, total_atendimentos, tamanho_lote):
        bloco = pendentes[inicio_bloco : inicio_bloco + tamanho_lote]
        textos_com_origem = []
        for id_, queixa, conduta in bloco:
            texto_base = f"{queixa}\n{conduta}"
            for ordem, pedaco in enumerate(dividir_em_chunks(texto_base, max_chars_chunk)):
                textos_com_origem.append((id_, ordem, pedaco))
        vetores = provedor.embed_passagens([t[2] for t in textos_com_origem])
        for (id_, ordem, pedaco), vetor in zip(textos_com_origem, vetores):
            lote_linhas.append(
                (id_, ordem, pedaco, _vetor_para_blob(vetor), provedor.nome_modelo, provedor.dimensoes)
            )
        _descarregar()
        processados = min(inicio_bloco + tamanho_lote, total_atendimentos)
        ritmo = inseridos / max(time.perf_counter() - inicio, 1e-6)
        print(
            f"[ingest] {processados:,}/{total_atendimentos:,} atendimentos | "
            f"{inseridos:,} chunks | {ritmo:.0f} chunks/s".replace(",", ".")
        )
    con.commit()
    total_geral = con.execute("SELECT COUNT(*) FROM prontuario_chunks").fetchone()[0]
    con.close()

    resumo = {
        "atendimentos": total_atendimentos,
        "chunks": inseridos,
        "total_na_tabela": total_geral,
        "modelo": provedor.nome_modelo,
        "dimensoes": provedor.dimensoes,
        "segundos": round(time.perf_counter() - inicio, 1),
    }
    print(
        f"=== Ingestão concluída ===\n"
        f"atendimentos novos: {resumo['atendimentos']:>8}\n"
        f"chunks inseridos:   {resumo['chunks']:>8}\n"
        f"total na tabela:    {resumo['total_na_tabela']:>8}\n"
        f"duração: {resumo['segundos']}s"
    )
    return resumo


def main() -> None:
    parser = argparse.ArgumentParser(description="Gera embeddings dos prontuários.")
    parser.add_argument("--provider", default="mock", choices=["mock", "openai", "local"])
    parser.add_argument("--db", type=Path, default=DB_PADRAO)
    parser.add_argument("--limite", type=int, default=50_000)
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--max-chars-chunk", type=int, default=600)
    argumentos = parser.parse_args()
    rodar_ingestao(
        provedor_nome=argumentos.provider,
        caminho_db=argumentos.db,
        limite=argumentos.limite,
        tamanho_lote=argumentos.batch_size,
        max_chars_chunk=argumentos.max_chars_chunk,
    )


if __name__ == "__main__":
    main()
