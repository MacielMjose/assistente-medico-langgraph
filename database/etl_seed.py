"""ETL: dataset_medpt_curado.parquet -> SQLite de prontuários simulados.

Uso:
    python database/etl_seed.py                          # carga completa (10.000 pacientes)
    python database/etl_seed.py --limite 50000           # amostra reduzida p/ iteração rápida
    python database/etl_seed.py --n-pacientes 1000 --seed 7

Cada linha do parquet torna-se um episódio de atendimento. Os episódios são
distribuídos entre pacientes sintéticos por especialidade principal (primeiro
átomo antes da vírgula), formando históricos coerentes e determinísticos.
"""

import argparse
import random
import sqlite3
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

import pyarrow.parquet as pq
from faker import Faker

RAIZ_PROJETO = Path(__file__).resolve().parents[1]
if str(RAIZ_PROJETO) not in sys.path:
    sys.path.insert(0, str(RAIZ_PROJETO))

from src.db.connection import aplicar_schema

SEED_PADRAO = 42
N_PACIENTES_PADRAO = 10_000
TAMANHO_LOTE = 25_000

DIRETORIO_DB = Path(__file__).resolve().parent
PARQUET_PADRAO = DIRETORIO_DB / "dataset_medpt_curado.parquet"
DB_PADRAO = DIRETORIO_DB / "assistente_medico.db"

UFs = ["SP", "RJ", "MG", "RS", "PR", "BA", "PE", "CE", "DF", "SC"]
DDDS = ["11", "21", "31", "41", "51", "61", "71", "81", "85"]

FAIXAS_ETARIAS_POR_CONDICAO = [
    (("tdah", "autismo", "adolescen", "infantil", "crianç"), (4, 17)),
    (("gravidez", "gestaç", "gestac", "pré-natal", "pre-natal"), (20, 39)),
    (("menopausa", "andropausa"), (45, 65)),
    (("próstata", "prostata", "alzheimer", "osteoporose", "parkinson"), (55, 88)),
]
FAIXA_ETARIA_PADRAO = (18, 80)

STATUS_CONDICAO = ("cronico", "resolvido", "ativo")
PESOS_STATUS = (45, 35, 20)

CATALOGO_EXAMES = [
    "Hemograma Completo",
    "Glicemia Em Jejum",
    "Colesterol Total E Frações",
    "Creatinina Sérica",
    "Ureia",
    "TSH",
    "T4 Livre",
    "Vitamina D (25-OH)",
    "Ácido Úrico",
    "Transaminases (TGO/TGP)",
    "Eletrocardiograma De Repouso",
    "Raio-X De Tórax",
    "Raio-X Da Região Afetada",
    "Ultrassonografia Abdominal Total",
    "Ultrassonografia Da Região Afetada",
    "Tomografia Computadorizada Da Região Afetada",
    "Ressonância Magnética Da Região Afetada",
    "Endoscopia Digestiva Alta",
    "Colonoscopia",
    "Eletroencefalograma",
    "Densitometria Óssea",
    "Mamografia",
    "Ultrassonografia Obstétrica",
    "Papanicolau",
    "Dosagem De Beta-HCG",
    "Sorologia Para HIV",
    "VDRL",
    "Cultura De Secreção",
    "Espirometria",
    "Teste De Esforço",
]

RESULTADOS_EXAME = [
    "Dentro dos parâmetros de referência",
    "Sem alterações significativas",
    "Alterado - reavaliação recomendada",
    "Alterado - encaminhar ao especialista",
    "Inconclusivo - repetir exame",
]

SQL_INSERIR_ATENDIMENTO = """
    INSERT INTO atendimentos
        (dataset_ref, paciente_id, profissional_id, condicao_id,
         tipo_questao_id, data_atendimento, queixa, conduta)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
"""


@dataclass
class ResumoETL:
    pacientes: int = 0
    profissionais: int = 0
    atendimentos: int = 0
    condicoes: int = 0
    especialidades: int = 0
    exames: int = 0
    duracao_segundos: float = 0.0
    avisos: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        linhas = [
            "=== Carga concluída ===",
            f"pacientes:      {self.pacientes:>8}",
            f"profissionais:  {self.profissionais:>8}",
            f"atendimentos:   {self.atendimentos:>8}",
            f"condições:      {self.condicoes:>8}",
            f"especialidades: {self.especialidades:>8}",
            f"exames:         {self.exames:>8}",
            f"duração:        {self.duracao_segundos:.1f}s",
        ]
        if self.avisos:
            linhas.append("avisos:")
            linhas.extend(f"  - {aviso}" for aviso in self.avisos)
        return "\n".join(linhas)


def _dividir_especialidades(valor: str) -> list[str]:
    return [parte.strip().title() for parte in valor.split(",") if parte.strip()]


def _faixa_etaria_para(nomes_condicoes: set[str]) -> tuple[int, int]:
    for palavras, faixa in FAIXAS_ETARIAS_POR_CONDICAO:
        for nome in nomes_condicoes:
            minusculo = nome.lower()
            if any(palavra in minusculo for palavra in palavras):
                return faixa
    return FAIXA_ETARIA_PADRAO


def _gerar_data_nascimento(faixa: tuple[int, int], rng: random.Random, hoje: date) -> str:
    anos = rng.randint(*faixa)
    nascimento = hoje - timedelta(days=anos * 365 + rng.randint(0, 364))
    return nascimento.isoformat()


class _GeradorDePopulacao:
    def __init__(self, seed: int):
        self._fake = Faker("pt_BR")
        self._fake.seed_instance(seed)
        self._rng = random.Random(seed)
        self._cpfs_usados: set[str] = set()
        self._registros_usados: set[str] = set()

    def novo_paciente(self, paciente_id: int, faixa_etaria: tuple[int, int]) -> tuple:
        sexo = self._rng.choice("MF")
        nome = self._fake.name_male() if sexo == "M" else self._fake.name_female()
        while True:
            bruto = self._fake.cpf()
            mascarado = f"***.{bruto[4:7]}.{bruto[8:11]}-**"
            if mascarado not in self._cpfs_usados:
                self._cpfs_usados.add(mascarado)
                break
        nascimento = _gerar_data_nascimento(faixa_etaria, self._rng, date.today())
        telefone = f"+55 ({self._rng.choice(DDDS)}) 9{self._rng.randint(10_000_000, 99_999_999)}"
        return (paciente_id, nome, mascarado, nascimento, sexo, telefone)

    def novo_profissional(self, profissional_id: int, especialidade_id: int) -> tuple:
        while True:
            registro = f"{self._rng.choice(UFs)}-{self._rng.randint(100_000, 999_999)}"
            if registro not in self._registros_usados:
                self._registros_usados.add(registro)
                break
        return (profissional_id, self._fake.name(), registro, especialidade_id)


def _alocar_pacientes_por_especialidade(
    demanda_por_especialidade: dict[str, int], n_pacientes: int
) -> dict[str, int]:
    total_episodios = sum(demanda_por_especialidade.values())
    cotas = {
        esp: max(1, round(demanda * n_pacientes / total_episodios))
        for esp, demanda in demanda_por_especialidade.items()
    }
    desvio = n_pacientes - sum(cotas.values())
    passo = 1 if desvio > 0 else -1
    ordenadas = sorted(cotas, key=lambda esp: -demanda_por_especialidade[esp])
    indice = 0
    while desvio != 0 and ordenadas:
        alvo = ordenadas[indice % len(ordenadas)]
        if passo > 0 or cotas[alvo] > 1:
            cotas[alvo] += passo
            desvio -= passo
        indice += 1
    return cotas


def _preparar_dimensoes_e_alocacao(parquet: pq.ParquetFile, total_linhas: int):
    leve = parquet.read(columns=["condition", "medical_specialty"])
    if total_linhas < parquet.metadata.num_rows:
        leve = leve.slice(0, total_linhas)

    coluna_condicao = leve.column("condition").to_pylist()
    nomes_condicoes = sorted(set(coluna_condicao))
    mapa_condicoes = {nome: i + 1 for i, nome in enumerate(nomes_condicoes)}
    rotulo_da_condicao = {i + 1: nome for i, nome in enumerate(nomes_condicoes)}

    ids_especialidades: dict[str, int] = {}
    episodios_por_especialidade: dict[str, list[int]] = defaultdict(list)
    condicao_da_linha = [0] * total_linhas
    for indice, bruto in enumerate(leve.column("medical_specialty").to_pylist()):
        atomos = _dividir_especialidades(bruto)
        for atomo in atomos:
            ids_especialidades.setdefault(atomo, len(ids_especialidades) + 1)
        episodios_por_especialidade[atomos[0]].append(indice)
        condicao_da_linha[indice] = mapa_condicoes[coluna_condicao[indice]]

    nomes_tipos = sorted(set(parquet.read(columns=["question_type"]).column("question_type").to_pylist()))
    mapa_tipos = {nome: i + 1 for i, nome in enumerate(nomes_tipos)}

    return (
        ids_especialidades,
        episodios_por_especialidade,
        condicao_da_linha,
        mapa_condicoes,
        mapa_tipos,
        rotulo_da_condicao,
    )


def rodar_etl(
    caminho_parquet: str | Path = PARQUET_PADRAO,
    caminho_db: str | Path = DB_PADRAO,
    n_pacientes: int = N_PACIENTES_PADRAO,
    limite_linhas: int | None = None,
    seed: int = SEED_PADRAO,
) -> ResumoETL:
    inicio = time.perf_counter()
    resumo = ResumoETL()
    gerador = _GeradorDePopulacao(seed)
    rng = random.Random(seed + 1)
    caminho_db = Path(caminho_db)
    caminho_db.parent.mkdir(parents=True, exist_ok=True)
    if caminho_db.exists():
        caminho_db.unlink()

    parquet = pq.ParquetFile(caminho_parquet)
    total_linhas = min(parquet.metadata.num_rows, limite_linhas or parquet.metadata.num_rows)
    agora = datetime.now()

    print(f"[etl] fase 0: dimensões e alocação ({total_linhas:,} episódios)...".replace(",", "."))
    (
        ids_especialidades,
        episodios_por_especialidade,
        condicao_da_linha,
        mapa_condicoes,
        mapa_tipos,
        rotulo_da_condicao,
    ) = _preparar_dimensoes_e_alocacao(parquet, total_linhas)

    conexao = sqlite3.connect(caminho_db)
    conexao.execute("PRAGMA journal_mode = OFF")
    conexao.execute("PRAGMA synchronous = OFF")
    conexao.execute("PRAGMA temp_store = MEMORY")
    conexao.execute("PRAGMA cache_size = -64000")
    conexao.execute("PRAGMA foreign_keys = ON")
    aplicar_schema(conexao)

    conexao.executemany(
        "INSERT INTO especialidades (id, nome) VALUES (?, ?)",
        [(id_, nome) for nome, id_ in sorted(ids_especialidades.items(), key=lambda item: item[1])],
    )
    conexao.executemany(
        "INSERT INTO tipos_questao (id, nome) VALUES (?, ?)",
        [(id_, nome) for nome, id_ in mapa_tipos.items()],
    )
    conexao.executemany(
        "INSERT INTO condicoes (id, nome) VALUES (?, ?)",
        [(id_, nome) for nome, id_ in mapa_condicoes.items()],
    )
    resumo.condicoes = len(mapa_condicoes)
    resumo.especialidades = len(ids_especialidades)

    cotas = _alocar_pacientes_por_especialidade(
        {esp: len(rows) for esp, rows in episodios_por_especialidade.items()}, n_pacientes
    )

    condicoes_por_paciente: dict[int, set[int]] = defaultdict(set)
    dono_da_linha: list[int] = [0] * total_linhas
    proximo_paciente_id = 1
    pacientes_por_especialidade: dict[str, list[int]] = {}
    for especialidade in sorted(episodios_por_especialidade):
        linhas_da_especialidade = episodios_por_especialidade[especialidade]
        rng.shuffle(linhas_da_especialidade)
        pacientes_da_especialidade = list(
            range(proximo_paciente_id, proximo_paciente_id + cotas[especialidade])
        )
        proximo_paciente_id += len(pacientes_da_especialidade)
        for posicao, linha in enumerate(linhas_da_especialidade):
            dono = pacientes_da_especialidade[posicao % len(pacientes_da_especialidade)]
            dono_da_linha[linha] = dono
            condicoes_por_paciente[dono].add(condicao_da_linha[linha])
        pacientes_por_especialidade[especialidade] = pacientes_da_especialidade

    pacientes_para_inserir = []
    base_temporal: dict[int, datetime] = {}
    cursor_temporal: dict[int, int] = {}
    for pid in range(1, n_pacientes + 1):
        nomes = {rotulo_da_condicao[cid] for cid in condicoes_por_paciente.get(pid, set())}
        faixa = _faixa_etaria_para(nomes)
        pacientes_para_inserir.append(gerador.novo_paciente(pid, faixa))
        base_temporal[pid] = agora - timedelta(days=rng.randint(365, 2190))
        cursor_temporal[pid] = 0
    del condicoes_por_paciente
    conexao.executemany(
        """
        INSERT INTO pacientes (id, nome, cpf_mascarado, data_nascimento, sexo, telefone_mock)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        pacientes_para_inserir,
    )
    resumo.pacientes = len(pacientes_para_inserir)

    profissionais_para_inserir = []
    vinculos_para_inserir = []
    profs_por_especialidade: dict[str, list[int]] = {}
    proximo_profissional_id = 1
    for especialidade in sorted(pacientes_por_especialidade):
        quantidade = 2 + len(pacientes_por_especialidade[especialidade]) // 2_000
        ids_locais = []
        especialidade_id = ids_especialidades[especialidade]
        for _ in range(quantidade):
            profissionais_para_inserir.append(
                gerador.novo_profissional(proximo_profissional_id, especialidade_id)
            )
            ids_locais.append(proximo_profissional_id)
            vinculos_para_inserir.append((proximo_profissional_id, especialidade_id))
            proximo_profissional_id += 1
        profs_por_especialidade[especialidade] = ids_locais
        if rng.random() < 0.30:
            outra = rng.choice(list(ids_especialidades.values()))
            vinculos_para_inserir.append((ids_locais[0], outra))
    conexao.executemany(
        """
        INSERT INTO profissionais (id, nome, registro_conselho, especialidade_principal_id)
        VALUES (?, ?, ?, ?)
        """,
        profissionais_para_inserir,
    )
    conexao.executemany(
        "INSERT OR IGNORE INTO profissional_especialidade (profissional_id, especialidade_id) VALUES (?, ?)",
        vinculos_para_inserir,
    )
    resumo.profissionais = len(profissionais_para_inserir)

    print("[etl] fase 1: streaming dos episódios de atendimento...")
    colunas = ["id", "question", "answer", "condition", "medical_specialty", "question_type"]
    inseridos = 0
    lote: list[tuple] = []
    concluido = False
    for bloco in parquet.iter_batches(batch_size=20_000, columns=colunas):
        dados = bloco.to_pydict()
        for posicao in range(bloco.num_rows):
            if inseridos >= total_linhas:
                concluido = True
                break
            paciente_id = dono_da_linha[inseridos]
            offset = cursor_temporal[paciente_id]
            cursor_temporal[paciente_id] = offset + rng.randint(1, 365)
            momento = base_temporal[paciente_id] + timedelta(days=offset)
            if momento > agora:
                momento = agora - timedelta(seconds=rng.randint(0, 86_399))
            atomos = _dividir_especialidades(dados["medical_specialty"][posicao])
            profissional_id = rng.choice(profs_por_especialidade[atomos[0]])
            lote.append(
                (
                    int(dados["id"][posicao]),
                    paciente_id,
                    profissional_id,
                    mapa_condicoes[dados["condition"][posicao]],
                    mapa_tipos[dados["question_type"][posicao]],
                    momento.isoformat(sep=" ", timespec="seconds"),
                    dados["question"][posicao],
                    dados["answer"][posicao],
                )
            )
            inseridos += 1
            if len(lote) >= TAMANHO_LOTE:
                conexao.executemany(SQL_INSERIR_ATENDIMENTO, lote)
                print(f"[etl]   {inseridos:,} episódios...".replace(",", "."))
                lote.clear()
        if concluido:
            break
    if lote:
        conexao.executemany(SQL_INSERIR_ATENDIMENTO, lote)
        lote.clear()
    resumo.atendimentos = inseridos
    del dono_da_linha, condicao_da_linha, episodios_por_especialidade

    print("[etl] fase 2: históricos, exames e índice full-text...")
    historicos = conexao.execute(
        """
        SELECT paciente_id, condicao_id, MIN(data_atendimento) AS primeiro
        FROM atendimentos
        GROUP BY paciente_id, condicao_id
        """
    ).fetchall()
    conexao.executemany(
        "INSERT INTO paciente_condicao (paciente_id, condicao_id, data_diagnostico, status) VALUES (?, ?, ?, ?)",
        [
            (
                pid,
                cid,
                datetime.fromisoformat(primeiro).date().isoformat(),
                rng.choices(STATUS_CONDICAO, weights=PESOS_STATUS)[0],
            )
            for pid, cid, primeiro in historicos
        ],
    )
    del historicos

    exames_para_inserir = []
    for atendimento_id, momento_bruto in conexao.execute(
        "SELECT id, data_atendimento FROM atendimentos"
    ).fetchall():
        if rng.random() > 0.28:
            continue
        dia_base = datetime.fromisoformat(momento_bruto)
        for _ in range(rng.choice((1, 1, 2))):
            dia_exame = min(dia_base + timedelta(days=rng.randint(0, 7)), agora).date()
            resultado = rng.choices(RESULTADOS_EXAME, weights=(38, 27, 15, 10, 10), k=1)[0]
            exames_para_inserir.append(
                (atendimento_id, rng.choice(CATALOGO_EXAMES), dia_exame.isoformat(), resultado)
            )
    conexao.executemany(
        """
        INSERT INTO exames (atendimento_id, nome_exame, data_exame, resultado)
        VALUES (?, ?, ?, ?)
        """,
        exames_para_inserir,
    )
    resumo.exames = len(exames_para_inserir)

    conexao.execute(
        """
        INSERT INTO atendimentos_fts (rowid, queixa, conduta)
        SELECT id, queixa, conduta FROM atendimentos
        """
    )

    violacoes = conexao.execute("PRAGMA foreign_key_check").fetchall()
    if violacoes:
        resumo.avisos.append(f"{len(violacoes)} violações de chave estrangeira detectadas")

    conexao.commit()
    conexao.execute("ANALYZE")
    conexao.commit()
    resumo.duracao_segundos = time.perf_counter() - inicio
    conexao.close()
    print(resumo)
    return resumo


def main() -> None:
    parser = argparse.ArgumentParser(description="Cria a base SQLite de prontuários simulados.")
    parser.add_argument("--parquet", type=Path, default=PARQUET_PADRAO)
    parser.add_argument("--db", type=Path, default=DB_PADRAO)
    parser.add_argument("--n-pacientes", type=int, default=N_PACIENTES_PADRAO)
    parser.add_argument("--limite", type=int, default=None, help="Máximo de episódios a carregar.")
    parser.add_argument("--seed", type=int, default=SEED_PADRAO)
    argumentos = parser.parse_args()
    rodar_etl(
        caminho_parquet=argumentos.parquet,
        caminho_db=argumentos.db,
        n_pacientes=argumentos.n_pacientes,
        limite_linhas=argumentos.limite,
        seed=argumentos.seed,
    )


if __name__ == "__main__":
    main()
