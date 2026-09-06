"""Carregamento de documentos de conhecimento via LangChain Document Loaders.

Fluxo:
    arquivo (PDF/Excel) -> LangChain Document Loader -> Document (com metadados)

Cada Document retornado carrega metadados de origem padronizados para permitir
rastreabilidade completa até o arquivo original:

    PDF:
        source          = nome do arquivo (ex.: "protocolo_asma.pdf")
        source_type     = "pdf"
        document_title  = título (nome do arquivo sem extensão, por padrão)
        page            = número da página (1-based)
        file_path       = caminho absoluto do arquivo

    Excel:
        source          = nome do arquivo (ex.: "transtornos_termicos.xlsx")
        source_type     = "excel"
        sheet           = nome da planilha (quando disponível)
        document_title  = título (nome do arquivo sem extensão, por padrão)
        file_path       = caminho absoluto do arquivo

Todos os loaders deste módulo são os Document Loaders oficiais do LangChain
(``PyPDFLoader`` e ``UnstructuredExcelLoader``). Nenhum parser manual é usado.
"""

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Iterable

from langchain_core.documents import Document

TIPO_PDF = "pdf"
TIPO_EXCEL = "excel"

EXTENSOES_SUPORTADAS = {
    ".pdf": TIPO_PDF,
    ".xlsx": TIPO_EXCEL,
    ".xls": TIPO_EXCEL,
}

SUFIXOS_TITULO = (
    ".pdf", ".xlsx", ".xls", ".PDF", ".XLSX", ".XLS",
)

# Campos de metadados externos (arquivo -> metadados reais da fonte).
# Usados para enriquecer chunks com a autoria/instituição/licença reais quando
# o arquivo está catalogado em "metadados_fontes.json" do corpus.
CAMPOS_METADADOS_EXTERNOS = (
    "document_title",
    "title",
    "author",
    "year",
    "institution",
    "license",
    "url",
    "document_type",
    "sintetico",
)


def _extrair_titulo(nome_arquivo: str, pagina_sufixo: str = "") -> str:
    """Deriva um título legível a partir do nome do arquivo.

    Ex.: "protocolo_asma.pdf" -> "protocolo asma"
         "transtornos_termicos.xlsx" -> "transtornos termicos"
    """
    nome, _ = os.path.splitext(nome_arquivo)
    nome = nome.replace("_", " ").replace("-", " ").strip()
    nome = re.sub(r"\s+", " ", nome).title()
    return f"{nome}{pagina_sufixo}"


def _nome_arquivo(caminho: str | Path) -> str:
    return Path(caminho).name


def _sanitizar_conteudo(texto: str | None) -> str:
    """Remove caracteres de controle que quebram campos text/JSONB no Postgres.

    NUL (0x00) e outros C0/DEL/C1 não são aceitos em colunas text/varchar do
    PostgreSQL. Trocamos por espaço (o conteúdo tabular/PDF é re-colapsado
    depois pelo splitter). Preserva tab, nova linha e CR.
    """
    return "".join(
        ch if (ch in "\t\n\r" or 0x20 <= ord(ch) < 0x7F or ord(ch) >= 0xA0) else " "
        for ch in (texto or "")
    )


def _normalizar_documento(
    doc: Document,
    caminho: str | Path,
    tipo: str,
    *,
    titulo_extra: str | None = None,
    pagina_extra: int | None = None,
    sheet_extra: str | None = None,
) -> Document:
    """Normaliza um Document do loader, padronizando os metadados de origem.

    Preserva quaisquer metadados já presentes e adiciona/sobrescreve os campos
    de rastreabilidade oficiais (source, source_type, document_title, page,
    sheet, file_path). O conteúdo é sanitizado (remove caracteres de controle).
    """
    caminho = Path(caminho)
    arquivo = _nome_arquivo(caminho)

    conteudo = _sanitizar_conteudo(doc.page_content)
    meta: dict = dict(doc.metadata or {})

    meta["source"] = arquivo
    meta["source_type"] = tipo
    meta["file_path"] = str(caminho.resolve())

    titulo = titulo_extra if titulo_extra else _extrair_titulo(arquivo)
    if pagina_extra is not None:
        titulo = f"{titulo} - p.{pagina_extra}"
    meta["document_title"] = titulo
    meta["title"] = titulo

    if pagina_extra is not None:
        meta["page"] = pagina_extra
    if sheet_extra is not None:
        meta["sheet"] = sheet_extra

    # Reconstruir o documento com os metadados padronizados
    return Document(
        page_content=conteudo,
        metadata=meta,
    )


def carregar_metadados_externos(caminho: str | Path) -> dict[str, dict]:
    """Carrega o catálogo de fontes do corpus (arquivo -> metadados reais).

    O catálogo segue o formato gerado por ``baixar_fontes_reais.py`` e pelo
    gerador de corpus sintético::

        {
            "versao": 1,
            "fontes": {
                "pcdt_asma_2021.pdf": {
                    "title": "Protocolo ... da Asma",
                    "author": "Ministério da Saúde / Conitec",
                    "year": "2021",
                    ...
                }
            }
        }

    Args:
        caminho: caminho do JSON de metadados (``metadados_fontes.json``).

    Returns:
        Dicionário ``{nome_do_arquivo: metadados}`` (vazio se não existir).
    """
    caminho = Path(caminho)
    if not caminho.is_file():
        return {}
    try:
        conteudo = json.loads(caminho.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    fontes = conteudo.get("fontes", {}) if isinstance(conteudo, dict) else {}
    return {str(nome): dict(meta) for nome, meta in fontes.items()}


def _aplicar_metadados_externos(
    doc: Document,
    arquivo: str,
    metadados_externos: dict[str, dict] | None,
    *,
    pagina_sufixo: str = "",
) -> Document:
    """Sobrescreve/enriquece os metadados do chunk com a fonte real catalogada.

    Quando o arquivo está no catálogo externo, o título passa a ser o título
    REAL da fonte (ex.: "Protocolo Clínico e Diretrizes Terapêuticas da Asma")
    seguido do localizador de página, e autor/instituição/ano/licença/URL são
    preenchidos a partir dos dados oficiais da publicação.

    Args:
        doc: Document já normalizado (com source/source_type/page/file_path).
        arquivo: nome do arquivo-fonte (ex.: "pcdt_asma_2021.pdf").
        metadados_externos: catálogo ``{arquivo: metadados}`` ou None.
        pagina_sufixo: sufixo de localização a preservar no título.

    Returns:
        Document com os metadados externos aplicados (inalterado se o arquivo
        não estiver no catálogo).
    """
    if not metadados_externos:
        return doc
    meta_fonte = metadados_externos.get(arquivo)
    if not meta_fonte:
        return doc

    meta = dict(doc.metadata or {})
    titulo_real = meta_fonte.get("title")
    if titulo_real:
        meta["document_title"] = f"{titulo_real}{pagina_sufixo}"
        meta["title"] = meta["document_title"]
    for campo in CAMPOS_METADADOS_EXTERNOS:
        if campo in meta_fonte and meta_fonte[campo] is not None:
            if campo in ("document_title", "title"):
                continue  # já tratado acima (mantém localizador de página)
            meta[campo] = meta_fonte[campo]

    return Document(
        page_content=doc.page_content,
        metadata=meta,
    )


def carregar_pdf(
    caminho: str | Path,
    metadata_externa: dict[str, dict] | None = None,
) -> list[Document]:
    """Carrega um PDF via PyPDFLoader, mantendo a informação de página.

    Cada página do PDF vira um Document com metadados de origem (source,
    source_type, page, document_title, file_path). O ``page`` é 1-based.
    Quando o arquivo está em ``metadata_externa``, os metadados reais da fonte
    (título, autor, instituição, ano, licença) são aplicados ao chunk.

    Args:
        caminho: caminho do arquivo PDF.
        metadata_externa: catálogo ``{nome_do_arquivo: metadados}`` opcional.

    Returns:
        Lista de Document (um por página com conteúdo não-vazio).
    """
    from langchain_community.document_loaders import PyPDFLoader

    caminho = Path(caminho)
    arquivo = _nome_arquivo(caminho)
    loader = PyPDFLoader(str(caminho))
    docs = loader.load()

    resultado: list[Document] = []
    for doc in docs:
        meta = doc.metadata or {}
        # PyPDFLoader usa "page" 0-based; normalizamos para 1-based.
        pagina_bruta = meta.get("page")
        pagina = None
        if isinstance(pagina_bruta, int):
            pagina = pagina_bruta + 1
        elif isinstance(pagina_bruta, str) and pagina_bruta.isdigit():
            pagina = int(pagina_bruta) + 1
        elif "page_number" in meta:
            pagina = meta.get("page_number")

        # Ignorar páginas sem conteúdo útil
        if not (doc.page_content or "").strip():
            continue

        normalizado = _normalizar_documento(
            doc,
            caminho,
            TIPO_PDF,
            pagina_extra=pagina,
        )
        sufixo = f" - p.{pagina}" if pagina is not None else ""
        resultado.append(
            _aplicar_metadados_externos(
                normalizado, arquivo, metadata_externa, pagina_sufixo=sufixo
            )
        )
    return resultado


def carregar_excel(
    caminho: str | Path,
    metadata_externa: dict[str, dict] | None = None,
) -> list[Document]:
    """Carrega uma planilha Excel via UnstructuredExcelLoader.

    Usa o loader oficial do LangChain em modo "elements", onde cada tabela
    (sheet) vira um elemento com metadata contendo ``page_name`` (nome da
    sheet), ``filename`` e ``text_as_html``.

    Args:
        caminho: caminho do arquivo .xlsx ou .xls.
        metadata_externa: catálogo ``{nome_do_arquivo: metadados}`` opcional.

    Returns:
        Lista de Document com metadados de origem (source, source_type,
        sheet, document_title, file_path).
    """
    from langchain_community.document_loaders import UnstructuredExcelLoader

    caminho = Path(caminho)
    arquivo = _nome_arquivo(caminho)
    loader = UnstructuredExcelLoader(str(caminho), mode="elements")
    docs = loader.load()

    resultado: list[Document] = []
    for doc in docs:
        meta = doc.metadata or {}
        sheet = meta.get("page_name") or meta.get("sheet") or meta.get("filename")
        # Limpar espaços extras no conteúdo tabular
        conteudo = re.sub(r"\s+", " ", doc.page_content or "").strip()
        if not conteudo:
            continue

        normalizado = _normalizar_documento(
            doc,
            caminho,
            TIPO_EXCEL,
            sheet_extra=sheet,
        )
        resultado.append(
            _aplicar_metadados_externos(normalizado, arquivo, metadata_externa)
        )
    return resultado


def carregar_documento(
    caminho: str | Path,
    metadata_externa: dict[str, dict] | None = None,
) -> list[Document]:
    """Detecta o tipo pelo sufixo e carrega via o loader do LangChain adequado.

    Args:
        caminho: caminho de um PDF (.pdf) ou planilha (.xlsx, .xls).
        metadata_externa: catálogo ``{nome_do_arquivo: metadados}`` opcional.

    Returns:
        Lista de Document.

    Raises:
        ValueError: se o formato não for suportado.
    """
    caminho = Path(caminho)
    sufixo = caminho.suffix.lower()
    if sufixo == ".pdf":
        return carregar_pdf(caminho, metadata_externa=metadata_externa)
    if sufixo in (".xlsx", ".xls"):
        return carregar_excel(caminho, metadata_externa=metadata_externa)
    raise ValueError(
        f"Formato não suportado: '{sufixo}'. "
        f"Formatos aceitos: {', '.join(sorted(EXTENSOES_SUPORTADAS))}"
    )


def carregar_diretorio(
    diretorio: str | Path,
    metadata_externa: dict[str, dict] | None = None,
) -> list[Document]:
    """Carrega todos os documentos suportados de um diretório (recursivo).

    Args:
        diretorio: caminho de um diretório contendo PDFs e/ou planilhas.
        metadata_externa: catálogo ``{nome_do_arquivo: metadados}`` opcional,
            aplicado aos chunks dos arquivos catalogados.

    Returns:
        Lista de Document de todos os arquivos suportados encontrados.
    """
    diretorio = Path(diretorio)
    arquivos: list[Path] = []
    for caminho in sorted(diretorio.rglob("*")):
        if caminho.is_file() and caminho.suffix.lower() in EXTENSOES_SUPORTADAS:
            arquivos.append(caminho)

    documentos: list[Document] = []
    for arquivo in arquivos:
        documentos.extend(carregar_documento(arquivo, metadata_externa=metadata_externa))
    return documentos


def gerar_chunk_id(doc: Document, indice: int = 0) -> str:
    """Gera um identificador estável de chunk para ingestão idempotente.

    É baseado no source + identificadores de localização (page/sheet) + o
    conteúdo hash — assim, reprocessar o mesmo arquivo gera os mesmos ids.

    Returns:
        Uma string no formato:
            <source>::<page|sheet>::<ordem>::<hash8>
    """
    meta = doc.metadata or {}
    source = meta.get("source", "arquivo")
    locator = meta.get("page") or meta.get("sheet") or "indice"
    conteudo_hash = hashlib.sha1(
        (doc.page_content or "").encode("utf-8")
    ).hexdigest()[:8]
    return f"{source}::{locator}::{indice}::{conteudo_hash}"


def documento_resumo(doc: Document) -> dict:
    """Resumo legível dos metadados de origem de um Document (p/ prints/log)."""
    meta = doc.metadata or {}
    partes = [meta.get("source_type", "?"), meta.get("source", "?")]
    if meta.get("page") is not None:
        partes.append(f"p.{meta['page']}")
    if meta.get("sheet"):
        partes.append(f"sheet:{meta['sheet']}")
    return {
        "origem": " | ".join(partes),
        "title": meta.get("document_title", meta.get("title", "")),
        "len_conteudo": len(doc.page_content or ""),
    }
