import hashlib
import math
import os

MODELO_OPENAI = "text-embedding-3-small"
DIMS_OPENAI = 1536

MODELO_E5 = "intfloat/multilingual-e5-small"
DIMS_E5 = 384

MODELO_MOCK = "mock-hash"
DIMS_MOCK = 64


def dividir_em_chunks(texto: str, max_chars: int = 600) -> list[str]:
    texto = " ".join(texto.split())
    if len(texto) <= max_chars:
        return [texto]
    chunks: list[str] = []
    atual: list[str] = []
    tamanho = 0
    for palavra in texto.split(" "):
        extra = len(palavra) + (1 if atual else 0)
        if atual and tamanho + extra > max_chars:
            chunks.append(" ".join(atual))
            atual = [palavra]
            tamanho = len(palavra)
        else:
            atual.append(palavra)
            tamanho += extra
    if atual:
        chunks.append(" ".join(atual))
    return chunks


def _normalizar(vetor: list[float]) -> list[float]:
    norma = math.sqrt(sum(x * x for x in vetor)) or 1.0
    return [x / norma for x in vetor]


class ProvedorEmbeddings:
    nome_modelo: str = ""
    dimensoes: int = 0

    def embed_passagens(self, textos: list[str]) -> list[list[float]]:
        raise NotImplementedError

    def embed_consulta(self, texto: str) -> list[float]:
        return self.embed_passagens([texto])[0]

    def verificar(self) -> None:
        self.embed_consulta("verificação de conectividade")


class EmbeddingsMock(ProvedorEmbeddings):
    def __init__(self, dimensoes: int = DIMS_MOCK):
        self.nome_modelo = MODELO_MOCK
        self.dimensoes = dimensoes

    def embed_passagens(self, textos: list[str]) -> list[list[float]]:
        vetores = []
        for texto in textos:
            digest = hashlib.md5(texto.encode("utf-8")).digest()
            semente = int.from_bytes(digest[:8], "little")
            estado = semente
            vetor = []
            for _ in range(self.dimensoes):
                estado = (estado * 6364136223846793005 + 1442695040888963407) % (1 << 64)
                vetor.append((estado >> 11) / float(1 << 53) - 0.5)
            vetores.append(_normalizar(vetor))
        return vetores


class EmbeddingsOpenAI(ProvedorEmbeddings):
    def __init__(self, modelo: str = MODELO_OPENAI):
        try:
            from openai import OpenAI
        except ImportError as erro:
            raise RuntimeError("Pacote 'openai' não instalado.") from erro
        chave = os.getenv("OPENAI_API_KEY")
        if not chave:
            raise RuntimeError(
                "OPENAI_API_KEY ausente. Atenção: a chave da Groq não funciona na API "
                "da OpenAI; cadastre uma chave válida em https://platform.openai.com."
            )
        self._cliente = OpenAI(api_key=chave)
        self.nome_modelo = modelo
        self.dimensoes = DIMS_OPENAI

    def embed_passagens(self, textos: list[str]) -> list[list[float]]:
        resposta = self._cliente.embeddings.create(model=self.nome_modelo, input=textos)
        ordenados = sorted(resposta.data, key=lambda item: item.index)
        return [item.embedding for item in ordenados]


class EmbeddingsE5Local(ProvedorEmbeddings):
    PREFIXO_PASSAGEM = "passage: "
    PREFIXO_CONSULTA = "query: "

    def __init__(self, modelo: str = MODELO_E5):
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as erro:
            raise RuntimeError(
                "sentence-transformers não instalado. Instale com: "
                "pip install torch --index-url https://download.pytorch.org/whl/cpu "
                "&& pip install -r requirements-local.txt"
            ) from erro
        self._modelo = SentenceTransformer(modelo)
        self.nome_modelo = modelo
        self.dimensoes = self._modelo.get_sentence_embedding_dimension()

    def embed_passagens(self, textos: list[str]) -> list[list[float]]:
        entradas = [self.PREFIXO_PASSAGEM + t for t in textos]
        matriz = self._modelo.encode(entradas, normalize_embeddings=True, show_progress_bar=False)
        return matriz.tolist()

    def embed_consulta(self, texto: str) -> list[float]:
        vetor = self._modelo.encode(
            self.PREFIXO_CONSULTA + texto, normalize_embeddings=True, show_progress_bar=False
        )
        return vetor.tolist()


def obter_provedor(nome: str) -> ProvedorEmbeddings:
    escolha = nome.strip().lower()
    if escolha == "mock":
        return EmbeddingsMock()
    if escolha == "openai":
        return EmbeddingsOpenAI()
    if escolha in ("local", "e5"):
        return EmbeddingsE5Local()
    raise ValueError(f"Provedor desconhecido: '{nome}'. Use: mock, openai ou local.")
