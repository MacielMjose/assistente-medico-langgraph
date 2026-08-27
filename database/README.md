# Base de prontuários simulados (PostgreSQL 17 + pgvector)

Este módulo popula a base estruturada de prontuários no **PostgreSQL em container**
(`docker-compose.yml`, na raiz do projeto) a partir do dataset curado
`dataset_medpt_curado.parquet` (384.084 perguntas e respostas médico-paciente em PT-BR).

Não existe mais instância SQLite no projeto: desenvolvimento, testes e produção
rodam sobre o mesmo servidor PostgreSQL+pgvector via Docker.

## Pré-requisitos

1. Python 3.12+ com ambiente virtual na raiz do projeto:

```bash
python -m venv .venv
source .venv/bin/activate        # Linux/macOS
# .venv\Scripts\activate         # Windows
```

2. Dependências instaladas (inclui `psycopg`, `pgvector` e o ecossistema LangChain):

```bash
pip install -r requirements.txt
```

3. Container PostgreSQL com a extensão pgvector:

```bash
docker compose -f docker-compose.yml up -d
```

O container expõe `localhost:5433` com o banco `assistente_medico`, usuário `medico`,
senha `medico_dev`.

4. O arquivo `database/dataset_medpt_curado.parquet` presente (ele não é versionado
   no git; copie-o do repositório compartilhado do grupo caso não o tenha).

## Gerar o banco

Na raiz do projeto, execute:

```bash
python database/etl_seed.py
```

A carga completa produz (a duração é maior que no antigo SQLite — alguns minutos):

| Entidade       | Volume    |
|----------------|-----------|
| pacientes      | 10.000    |
| profissionais  | ~355      |
| atendimentos   | 384.084   |
| condições      | 3.288     |
| especialidades | 104       |
| exames         | ~143.000  |
| agendamentos   | ~50.000   |

O script **apaga e recria todo o schema public** antes de recomeçar, portanto é
sempre seguro reexecutar.

## Opções da linha de comando

```bash
python database/etl_seed.py [opções]
```

| Opção            | Padrão                                | Descrição                                        |
|------------------|---------------------------------------|--------------------------------------------------|
| `--parquet`      | `database/dataset_medpt_curado.parquet` | Caminho do dataset de origem                    |
| `--dsn`          | env `MEDPT_PG_DSN` (caso contrário, `medico:medico_dev@localhost:5433/assistente_medico`) | DSN do PostgreSQL |
| `--n-pacientes`  | `10000`                               | Quantidade de pacientes sintéticos                |
| `--limite`       | todas as linhas                       | Máximo de episódios a carregar (amostra p/ teste) |
| `--seed`         | `42`                                  | Semente aleatória (mesma seed = mesma base)       |

Exemplos:

```bash
# amostra rápida para iterar sem carregar tudo
python database/etl_seed.py --limite 20000

# base menor, outra distribuição de pacientes
python database/etl_seed.py --n-pacientes 1000 --seed 7
```

## Como os dados são gerados

O parquet não identifica pacientes, então cada linha vira um episódio de atendimento
e os episódios são distribuídos entre pacientes sintéticos pela especialidade principal
(primeiro nome antes da vírgula em `medical_specialty`). Com isso cada paciente acumula
um histórico coerente (~38 consultas em média, concentradas na área dele).

Tudo é derivado da semente fixa: rodar duas vezes com a mesma seed produz exatamente
a mesma base. Dados pessoais são fictícios (Faker pt-BR): CPF mascarado, telefone fake,
datas plausíveis conforme a condição. Nenhum dado real é usado.

## Ingestão de embeddings (busca semântica)

A busca vetorial usa o **vector store do LangChain (PGVector)**: o LangChain cria e
gerencia as tabelas `langchain_pg_collection` / `langchain_pg_embedding` (PostgreSQL +
pgvector), com os metadados dos chunks em JSONB. Não há mais a tabela manual
`prontuario_chunks`.

```bash
# embeddings fake (determinísticos pelo conteúdo do texto), ideal p/ testes e desenvolvimento
python database/embeddings_ingest.py --provider mock --limite 50000

# embeddings reais OpenAI (exige OPENAI_API_KEY)
python database/embeddings_ingest.py --provider openai --limite 50000
```

A ingestão é **retomável**: atendimentos já vetorizados na coleção do provedor são pulados.

Ao trocar de provedor/modelo, use `--reset-colecao` para apagar os vetores da coleção
do provedor antes de reingerir (útil especialmente no mock, cujo `DeterministicFakeEmbedding`
muda o vetor se a implementação mudar). O vetor mock é o `DeterministicFakeEmbedding` do
`langchain-core` (determinístico pelo conteúdo do texto, sem chave de API).

O provedor é escolhido por coleção (`assistente_medico_<modelo>`), então vetores de
modelos diferentes nunca se misturam.

## Busca

```python
from src.db.buscar import BuscaRepositorio
from src.db.embeddings import obter_provedor

busca = BuscaRepositorio()

# busca textual (full-text em português)
busca.buscar_texto("dor lombar", condicao="Hérnia Inguinal", limite=5)

# busca semântica (LangChain/PGVector)
busca.buscar_vetorial("dor lombar ao levantar peso", obter_provedor("mock"), k=5)
```

## Validar a base gerada

Os testes de integração exigem o container no ar:

```bash
docker compose -f docker-compose.yml up -d
MEDPT_TESTAR_PG=1 python -m pytest tests/ -v
```

- `tests/test_schema_etl.py`: executa um mini-ETL em um banco de teste isolado
  (`assistente_medico_test`) e valida schema, integridade e repositórios.
- `tests/test_embeddings.py`: mini-ETL + ingestão mock + busca vetorial com filtros.
- `tests/test_base_pg.py`: valida contagens/integridade/busca na base completa do dev.

Sem `MEDPT_TESTAR_PG` (ou sem o container), os testes do marcador `pg` são pulados.

Uso rápido pelo interpretador:

```python
from src.db.repos import PacienteRepositorio, EstatisticaRepositorio

print(EstatisticaRepositorio().estatisticas())
PacienteRepositorio().buscar_paciente("Maria", limite=3)
```

## Problemas comuns

| Sintoma | Causa provável | Solução |
|---------|----------------|---------|
| `Connection refused` ao rodar o ETL/repositório | Container parado | `docker compose -f docker-compose.yml up -d` |
| `undefined table` / `relation does not exist` | Schema não criado | Rodar `python database/etl_seed.py` (recria o schema) |
| `ModuleNotFoundError: No module named 'src'` | Executado fora da raiz | Rodar sempre a partir da raiz do projeto |
| `FileNotFoundError` do parquet no início do ETL | Dataset ausente | Copiar `dataset_medpt_curado.parquet` para `database/` |
| `OPENAI_API_KEY` ausente ao usar `--provider openai` | Sem chave | Usar `mock` ou definir a variável de ambiente |

## Estrutura de scripts SQL

O schema do banco está dividido em arquivos individuais por tabela/view em
`database/scripts/postgres/`:

```
database/scripts/postgres/
  00_init.sql                          CREATE EXTENSION vector
  01_especialidades.table.sql          CREATE TABLE especialidades
  02_condicoes.table.sql               CREATE TABLE condicoes
  03_tipos_questao.table.sql           CREATE TABLE tipos_questao
  04_profissionais.table.sql           CREATE TABLE profissionais
  05_profissional_especialidade.table.sql
  06_pacientes.table.sql               CREATE TABLE pacientes
  07_paciente_condicao.table.sql
  08_atendimentos.table.sql            CREATE TABLE atendimentos + TSVECTOR `busca` (GIN)
  09_exames.table.sql                  CREATE TABLE exames
  10_agendamentos.table.sql            CREATE TABLE agendamentos
  12_log_auditoria.table.sql           CREATE TABLE log_auditoria
  13_pgvector_filter.sql               Sobrecarga jsonb_path_match p/ PGVector
  14_vw_historico_paciente.view.sql
  15_vw_exames_paciente.view.sql
  16_vw_estatisticas_base.view.sql
```

Observações:

- A busca textual usa a coluna gerada `atendimentos.busca` (TSVECTOR em português)
  com índice GIN — nada é populado manualmente no ETL.
- A busca vetorial **não tem script** de tabela: `langchain_pg_collection` e
  `langchain_pg_embedding` são criadas pelo vector store do LangChain na primeira
  ingestão.
- `13_pgvector_filter.sql` cria uma sobrecarga de `jsonb_path_match` que aceita
  VARCHAR nos argumentos 2 e 3 (como o PGVector clássico os gera); no PG 17 não
  há cast implícito, então sem ela os filtros por metadados falham.
- O prefixo numérico garante a ordem correta de criação (respeitando dependências FK).

### Regenerar o schema monolítico

O arquivo `database/schema_postgres.sql` é **auto-gerado** a partir dos scripts:

```bash
python database/rebuild_schema.py
```

O código Python (`src/db/connection.py`) lê os scripts individuais; o arquivo
monolítico existe apenas como conveniência/alias.