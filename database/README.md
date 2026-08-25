# Base de prontuários simulados (SQLite)

Este módulo gera a base estruturada de prontuários (`assistente_medico.db`) a partir do
dataset curado `dataset_medpt_curado.parquet` (384.084 perguntas e respostas médico-paciente em PT-BR).

## Pré-requisitos

1. Python 3.12+ com ambiente virtual na raiz do projeto:

```bash
python -m venv .venv
source .venv/bin/activate        # Linux/macOS
# .venv\Scripts\activate         # Windows
```

2. Dependências instaladas:

```bash
pip install -r requirements.txt
```

3. O arquivo `database/dataset_medpt_curado.parquet` presente (ele não é versionado no git;
   copie-o do repositório compartilhado do grupo caso não o tenha).

## Gerar o banco

Na raiz do projeto, execute:

```bash
python database/etl_seed.py
```

Isso cria `database/assistente_medico.db` (~420 MB) em cerca de 25 segundos, com:

| Entidade       | Volume    |
|----------------|-----------|
| pacientes      | 10.000    |
| profissionais  | ~194      |
| atendimentos   | 384.084   |
| condições      | 3.288     |
| especialidades | 104       |
| exames         | ~143.000  |

O script apaga um `.db` anterior antes de recomeçar, portanto é sempre seguro reexecutar.

## Opções da linha de comando

```bash
python database/etl_seed.py [opções]
```

| Opção            | Padrão                                | Descrição                                        |
|------------------|---------------------------------------|--------------------------------------------------|
| `--parquet`      | `database/dataset_medpt_curado.parquet` | Caminho do dataset de origem                    |
| `--db`           | `database/assistente_medico.db`       | Caminho do SQLite gerado                          |
| `--n-pacientes`  | `10000`                               | Quantidade de pacientes sintéticos                |
| `--limite`       | todas as linhas                       | Máximo de episódios a carregar (amostra p/ teste) |
| `--seed`         | `42`                                  | Semente aleatória (mesma seed = mesma base)       |

Exemplos:

```bash
# amostra rápida (~3 s) para iterar sem carregar tudo
python database/etl_seed.py --limite 20000 --db database/teste_rapido.db

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

## Validar a base gerada

```bash
python -m pytest tests/ -v
```

- `tests/test_schema_etl.py`: roda um mini-ETL isolado (não depende da base completa).
- `tests/test_base_completa.py`: valida contagens, integridade referencial e busca textual
  na base real (pula automaticamente se `assistente_medico.db` ainda não existe).

Teste rápido pelo interpretador:

```python
from src.db.repository import RepositorioClinico

repo = RepositorioClinico()
print(repo.estatisticas())
repo.buscar_paciente("Maria", limite=3)
repo.buscar_texto("dor lombar")
```

## Problemas comuns

| Sintoma | Causa provável | Solução |
|---------|----------------|---------|
| `Base não encontrada ...` ao usar o repositório | `.db` ainda não foi gerado | Rodar `python database/etl_seed.py` |
| `ModuleNotFoundError: No module named 'src'` | Executado fora da raiz | Rodar sempre a partir da raiz do projeto |
| `FileNotFoundError` do parquet no início do ETL | Dataset ausente | Copiar `dataset_medpt_curado.parquet` para `database/` |

O arquivo `.db` está no `.gitignore`; os scripts SQL e `etl_seed.py` são versionados,
pois qualquer pessoa do grupo consegue regenerar a base localmente.

## Estrutura de scripts SQL

O schema do banco está dividido em arquivos individuais por tabela/view:

```
database/
  scripts/
    sqlite/
      00_init.sql                          PRAGMA foreign_keys = ON
      01_especialidades.table.sql          CREATE TABLE especialidades
      02_condicoes.table.sql               CREATE TABLE condicoes
      03_tipos_questao.table.sql           CREATE TABLE tipos_questao
      04_profissionais.table.sql           CREATE TABLE profissionais
      05_profissional_especialidade.table.sql
      06_pacientes.table.sql               CREATE TABLE pacientes
      07_paciente_condicao.table.sql
      08_atendimentos.table.sql            CREATE TABLE atendimentos + índices
      09_exames.table.sql                  CREATE TABLE exames
      10_agendamentos.table.sql            CREATE TABLE agendamentos
      11_prontuario_chunks.table.sql       CREATE TABLE prontuario_chunks
      12_log_auditoria.table.sql           CREATE TABLE log_auditoria
      13_atendimentos_fts.table.sql        FTS5 (busca textual)
      14_vw_historico_paciente.view.sql
      15_vw_exames_paciente.view.sql
      16_vw_estatisticas_base.view.sql
    postgres/
      00_init.sql                          CREATE EXTENSION vector
      ... (mesma estrutura, sintaxe PG)
```

O prefixo numérico garante a ordem correta de criação (respeitando dependências FK).

### Regenerar os schemas monolíticos

Os arquivos `schema.sql` e `schema_postgres.sql` na raiz de `database/` são
**auto-gerados** a partir dos scripts individuais:

```bash
python database/rebuild_schema.py
```

O código Python (`connection.py`, `migrate_sqlite_to_pg.py`) lê os scripts
individualmente — os arquivos monolíticos existem apenas como conveniência/alias.
