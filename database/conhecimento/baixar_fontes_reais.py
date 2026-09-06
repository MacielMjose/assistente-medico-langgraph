"""Download do corpus documental real (PDFs oficiais) para o conhecimento RAG.

Baixa protocolos clínicos (PCDT) e manuais oficiais publicados pelo Ministério
da Saúde / Conitec / BVS-MS em português e registra os metadados de cada fonte
(público, instituição, ano, licença) em ``knowledge/metadados_fontes.json`` para
rastreabilidade do corpus.

O download é tolerante a falhas: cada fonte falha individualmente com aviso,
sem interromper as demais. A integridade é validada pelos "magic bytes" (%%PDF).
URLs que retornam HTML (páginas de visualização do gov.br) são detectadas e
reportadas como URL imprópria, sem gravar arquivo inválido.

Uso:
    python database/conhecimento/baixar_fontes_reais.py
    python database/conhecimento/baixar_fontes_reais.py --forcar
    python database/conhecimento/baixar_fontes_reais.py --destino knowledge/pdf --timeout 180

Saída:
    knowledge/pdf/          PDFs oficiais baixados (não versionados no git)
    knowledge/metadados_fontes.json   metadados de todas as fontes do corpus
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

RAIZ_PROJETO = Path(__file__).resolve().parents[2]
PADRAO_DESTINO = RAIZ_PROJETO / "knowledge" / "pdf"
PADRAO_METADADOS = RAIZ_PROJETO / "knowledge" / "metadados_fontes.json"

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

LICENCA_OFICIAL_MS = (
    "É permitida a reprodução parcial ou total desta obra, desde que citada a "
    "fonte e que não seja para venda ou qualquer fim comercial "
    "(Ministério da Saúde)."
)

# ── Fontes reais confirmadas (PCDTs do Conitec/MS, manuais da BVS-MS) ─────────
# Cada entrada lista a URL primária e, opcionalmente, alternativas. A primeira
# URL que baixar um PDF válido é mantida.
FONTES_REAIS: list[dict] = [
    {
        "filename": "pcdt_asma_2021.pdf",
        "title": "Protocolo Clínico e Diretrizes Terapêuticas da Asma",
        "author": "Ministério da Saúde / Conitec",
        "institution": "Ministério da Saúde (Conitec)",
        "year": "2021",
        "document_type": "pcdt",
        "urls": [
            "https://www.gov.br/saude/pt-br/assuntos/pcdt/a/asma-portaria-conjunta-saes-sectics-no-32/view",
            "https://www.gov.br/conitec/pt-br/midias/protocolos/20210830_pcdt_asma_pt14.pdf/@@display-file/file",
        ],
    },
    {
        "filename": "pcdt_hipertensao_2025.pdf",
        "title": "Protocolo Clínico e Diretrizes Terapêuticas da Hipertensão Arterial Sistêmica",
        "author": "Ministério da Saúde / Conitec",
        "institution": "Ministério da Saúde (Conitec)",
        "year": "2025",
        "document_type": "pcdt",
        "urls": [
            "https://www.gov.br/conitec/pt-br/midias/protocolos/pcdt-hipertensao-arterial-sistemica.pdf/@@display-file/file",
        ],
    },
    {
        "filename": "pcdt_diabete_melito_tipo2_2026.pdf",
        "title": "Protocolo Clínico e Diretrizes Terapêuticas do Diabete Melito Tipo 2",
        "author": "Ministério da Saúde / Conitec",
        "institution": "Ministério da Saúde (Conitec)",
        "year": "2026",
        "document_type": "pcdt",
        "urls": [
            "https://www.gov.br/conitec/pt-br/midias/protocolos/2026/pcdt-diabete-melito-tipo-2/@@display-file/file",
        ],
    },
    {
        "filename": "pcdt_diabete_melito_tipo1_resumido.pdf",
        "title": "Protocolo Clínico e Diretrizes Terapêuticas do Diabete Melito Tipo 1 (versão resumida)",
        "author": "Ministério da Saúde / Conitec",
        "institution": "Ministério da Saúde (Conitec)",
        "year": "2019",
        "document_type": "pcdt",
        "urls": [
            "https://www.gov.br/conitec/pt-br/midias/protocolos/resumidos/pcdt_resumido_diabetesmellitus_tipo1.pdf/@@display-file/file",
            "https://www.gov.br/conitec/pt-br/midias/protocolos/resumidos/pcdt_resumido_diabetesmellitus_tipo1.pdf",
        ],
    },
    {
        "filename": "pcdt_artrite_reumatoide.pdf",
        "title": "Protocolo Clínico e Diretrizes Terapêuticas da Artrite Reumatoide",
        "author": "Ministério da Saúde / Conitec",
        "institution": "Ministério da Saúde (Conitec)",
        "year": "2021",
        "document_type": "pcdt",
        "urls": [
            "https://www.gov.br/conitec/pt-br/midias/protocolos/pcdt-da-artrite-reumatoide/@@display-file/file",
        ],
    },
    {
        "filename": "pcdt_epilepsia.pdf",
        "title": "Protocolo Clínico e Diretrizes Terapêuticas da Epilepsia",
        "author": "Ministério da Saúde / Conitec",
        "institution": "Ministério da Saúde (Conitec)",
        "year": "2019",
        "document_type": "pcdt",
        "urls": [
            "https://www.gov.br/conitec/pt-br/midias/protocolos/pcdt_epilepsia.pdf/@@display-file/file",
            "https://www.gov.br/conitec/pt-br/midias/protocolos/pcdt_epilepsia.pdf",
        ],
    },
    {
        "filename": "pcdt_glaucoma_resumido.pdf",
        "title": "Protocolo Clínico e Diretrizes Terapêuticas do Glaucoma (versão resumida)",
        "author": "Ministério da Saúde / Conitec",
        "institution": "Ministério da Saúde (Conitec)",
        "year": "2020",
        "document_type": "pcdt",
        "urls": [
            "https://www.gov.br/conitec/pt-br/midias/protocolos/resumidos/PCDTResumidoGlaucomafinal.pdf/@@display-file/file",
            "https://www.gov.br/conitec/pt-br/midias/protocolos/resumidos/PCDTResumidoGlaucomafinal.pdf",
        ],
    },
    {
        "filename": "pcdt_esclerose_multipla_2024.pdf",
        "title": "Protocolo Clínico e Diretrizes Terapêuticas da Esclerose Múltipla",
        "author": "Ministério da Saúde / Conitec",
        "institution": "Ministério da Saúde (Conitec)",
        "year": "2024",
        "document_type": "pcdt",
        "urls": [
            "https://saude.rs.gov.br/upload/arquivos/202410/01155947-pcdt-de-esclerose-multipla-2024.pdf",
        ],
    },
    {
        "filename": "pcdt_hiv_modulo2_2024.pdf",
        "title": "Protocolo Clínico e Diretrizes Terapêuticas para Manejo da Infecção pelo HIV (Módulo 2)",
        "author": "Ministério da Saúde / DATHI",
        "institution": "Ministério da Saúde (Departamento de HIV/Aids)",
        "year": "2024",
        "document_type": "pcdt",
        "urls": [
            "http://www.gov.br/aids/pt-br/central-de-conteudo/pcdts/PCDT_HIV_Modulo_2_2024_eletrnicoISBN.pdf/@@display-file/file",
        ],
    },
    {
        "filename": "pcdt_hepatite_b_2016.pdf",
        "title": "Relatório de Recomendação PCDT Hepatite B e Coinfecções",
        "author": "Ministério da Saúde / Conitec",
        "institution": "Ministério da Saúde (Conitec)",
        "year": "2016",
        "document_type": "relatorio_pcdt",
        "urls": [
            "https://www.gov.br/conitec/pt-br/midias/relatorios/2016/relatorio_pcdt_hepatitebcoinfeccoes_final.pdf/@@display-file/file",
        ],
    },
    {
        "filename": "pcdt_parkinson.pdf",
        "title": "Protocolo Clínico e Diretrizes Terapêuticas da Doença de Parkinson",
        "author": "Ministério da Saúde / Conitec",
        "institution": "Ministério da Saúde (Conitec)",
        "year": "2022",
        "document_type": "pcdt",
        "urls": [
            "https://www.gov.br/conitec/pt-br/midias/protocolos/pcdt-doenca-de-parkinson/@@display-file/file",
        ],
    },
    {
        "filename": "pcdt_sobrepeso_obesidade_2020.pdf",
        "title": "Protocolo Clínico e Diretrizes Terapêuticas de Sobrepeso e Obesidade em Adultos",
        "author": "Ministério da Saúde / Conitec",
        "institution": "Ministério da Saúde (Conitec)",
        "year": "2020",
        "document_type": "pcdt",
        "urls": [
            "https://www.gov.br/conitec/pt-br/midias/protocolos/20201113_pcdt_sobrepeso_e_obesidade_em_adultos_29_10_2020_final.pdf/@@display-file/file",
        ],
    },
    {
        "filename": "pcdt_dpoc_2021.pdf",
        "title": "Protocolo Clínico e Diretrizes Terapêuticas da Doença Pulmonar Obstrutiva Crônica (Relatório de Recomendação nº 651)",
        "author": "Ministério da Saúde / Conitec",
        "institution": "Ministério da Saúde (Conitec)",
        "year": "2021",
        "document_type": "pcdt",
        "urls": [
            "https://www.gov.br/conitec/pt-br/midias/relatorios/2021/20211123_relatorio_dpoc_651.pdf/@@display-file/file",
        ],
    },
    {
        "filename": "livro_pcdt_volume_iii_2014.pdf",
        "title": "Protocolos Clínicos e Diretrizes Terapêuticas do Ministério da Saúde (Volume III)",
        "author": "Ministério da Saúde / Conitec",
        "institution": "Ministério da Saúde (Conitec)",
        "year": "2014",
        "document_type": "livro_pcdt",
        "urls": [
            "http://antigo-conitec.saude.gov.br/images/Protocolos/Livros/LivroPCDT_VolumeIII.pdf",
        ],
    },
    {
        "filename": "regulacao_medica_urgencias.pdf",
        "title": "Regulação Médica das Urgências (Ministério da Saúde)",
        "author": "Ministério da Saúde",
        "institution": "Ministério da Saúde (BVS-MS)",
        "year": "2014",
        "document_type": "manual",
        "urls": [
            "https://www.gov.br/saude/pt-br/composicao/saes/samu-192/publicacoes/regulacao_medica_urgencias.pdf/@@display-file/file",
            "https://www.gov.br/saude/pt-br/composicao/saes/samu-192/publicacoes/regulacao_medica_urgencias.pdf",
        ],
    },
    {
        "filename": "politica_nacional_atencao_urgencias_3ed.pdf",
        "title": "Política Nacional de Atenção às Urgências (3ª edição)",
        "author": "Ministério da Saúde",
        "institution": "Ministério da Saúde (BVS-MS)",
        "year": "2006",
        "document_type": "manual",
        "urls": [
            "https://bvsms.saude.gov.br/bvs/publicacoes/politica_nacional_atencao_urgencias_3ed.pdf",
            "https://www.ribeiraopreto.sp.gov.br/files/ssaude/pdf/ap-politica-nacional-atencaourgencias-manual.pdf",
        ],
    },
    {
        "filename": "manual_instrutivo_rue.pdf",
        "title": "Manual Instrutivo da Rede de Atenção às Urgências e Emergências no SUS",
        "author": "Ministério da Saúde",
        "institution": "Ministério da Saúde (protocolo aprovado)",
        "year": "2013",
        "document_type": "manual",
        "urls": [
            "https://biblioteca.cofen.gov.br/wp-content/uploads/2024/07/manual-instrutivo-rede-atencao-urgencias-emergencias-sistema-unico-saude.pdf",
        ],
    },
]


def _cabecalhos() -> dict:
    return {
        "User-Agent": USER_AGENT,
        "Accept": "application/pdf,application/octet-stream,*/*",
        "Accept-Language": "pt-BR,pt;q=0.9",
    }


def baixar_pdf(url: str, destino: Path, timeout: int) -> tuple[bool, str]:
    """Baixa a URL e grava em ``destino`` se o conteúdo for um PDF válido.

    Retorna ``(ok, mensagem)``; nunca cria arquivo se o conteúdo não for PDF
    (ex.: página HTML de visualização do gov.br).
    """
    req = urllib.request.Request(url, headers=_cabecalhos())
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            cabecalho = resp.read(5)
            if not cabecalho.startswith(b"%PDF"):
                return False, f"conteúdo não é PDF (primeiros bytes: {cabecalho!r})"
            corpo = cabecalho + resp.read()
    except urllib.error.HTTPError as exc:
        return False, f"HTTP {exc.code}"
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return False, f"erro de rede: {exc.reason if hasattr(exc, 'reason') else exc}"

    destino.write_bytes(corpo)
    return True, f"{len(corpo) / 1024:.0f} KB salvos"


def baixar_fonte(fonte: dict, destino: Path, timeout: int, forcar: bool) -> dict:
    """Baixa uma fonte tentando as URLs em ordem. Retorna o metadado atualizado."""
    arquivo = destino / fonte["filename"]
    if arquivo.exists() and not forcar:
        meta = dict(fonte)
        meta["baixado"] = True
        meta["url"] = fonte["urls"][0]
        return meta

    for url in fonte["urls"]:
        ok, msg = baixar_pdf(url, arquivo, timeout)
        if ok:
            meta = dict(fonte)
            meta["baixado"] = True
            meta["url"] = url
            print(f"[ok]     {fonte['filename']}  ({msg})")
            return meta
        print(f"[aviso]  {fonte['filename']} <- {url}\n         {msg}")
    print(f"[falha]  {fonte['filename']}: nenhuma URL produziu PDF válido.")
    return dict(fonte) | {"baixado": False, "url": fonte["urls"][0]}


def _carregar_existente() -> dict:
    if PADRAO_METADADOS.exists():
        try:
            return json.loads(PADRAO_METADADOS.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {"versao": 1, "fontes": {}}
    return {"versao": 1, "fontes": {}}


def salvar_metadados(fontes: list[dict]) -> None:
    existente = _carregar_existente()
    fontes_json = existente.get("fontes", {})
    for fonte in fontes:
        entrada = {
            "title": fonte["title"],
            "author": fonte["author"],
            "institution": fonte["institution"],
            "year": fonte["year"],
            "document_type": fonte["document_type"],
            "license": LICENCA_OFICIAL_MS,
            "url": fonte["url"],
            "sintetico": fonte.get("sintetico", False),
            "baixado": fonte.get("baixado", False),
        }
        if fonte.get("isbn"):
            entrada["isbn"] = fonte["isbn"]
        fontes_json[fonte["filename"]] = entrada

    PADRAO_METADADOS.parent.mkdir(parents=True, exist_ok=True)
    PADRAO_METADADOS.write_text(
        json.dumps(
            {
                "versao": 1,
                "gerado_em": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                "fontes": dict(sorted(fontes_json.items())),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Baixa o corpus documental real (PDFs oficiais).")
    parser.add_argument(
        "--destino",
        type=str,
        default=None,
        help="Diretório de destino dos PDFs (padrão: knowledge/pdf).",
    )
    parser.add_argument("--timeout", type=int, default=120, help="Timeout por download (s).")
    parser.add_argument(
        "--forcar", action="store_true", help="Re-baixa mesmo se o arquivo já existir."
    )
    parser.add_argument(
        "--lista", action="store_true", help="Apenas lista as fontes configuradas e sai."
    )
    args = parser.parse_args()

    if args.lista:
        for fonte in FONTES_REAIS:
            print(f"{fonte['filename']:48s} {fonte['year']:5s} {fonte['document_type']:18s} {fonte['title']}")
        return

    destino = Path(args.destino) if args.destino else PADRAO_DESTINO
    destino.mkdir(parents=True, exist_ok=True)

    print(f"[info] destino: {destino}")
    print(f"[info] fontes configuradas: {len(FONTES_REAIS)}")
    print(f"[info] metadados: {PADRAO_METADADOS}")
    print("-" * 70)

    baixados = 0
    for fonte in FONTES_REAIS:
        meta = baixar_fonte(fonte, destino, args.timeout, args.forcar)
        salvar_metadados([meta])
        if meta.get("baixado"):
            baixados += 1

    print("-" * 70)
    print(f"Resumo: {baixados}/{len(FONTES_REAIS)} fontes baixadas em {destino}")
    print(f"Metadados atualizados em {PADRAO_METADADOS}")


if __name__ == "__main__":
    sys.exit(main())