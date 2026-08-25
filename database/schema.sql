-- ============================================================================
-- Schema simulado de prontuários médicos (SQLite)
-- Projeto: assistente-medico-langgraph
-- *** ARQUIVO AUTO-GERADO *** Execute: python database/rebuild_schema.py
--
-- Convenções:
--   * ids INTEGER PRIMARY KEY (rowid alias, sem autoincrement explícito)
--   * datas em ISO-8601; DATE/DATETIME convertidos via detect_types
--   * FTS5 externo a atendimentos: populado pelo ETL (carga read-only)
--   * prontuario_chunks.embedding BLOB = float32 little-endian empacotado;
--     na migração p/ Postgres+pgvector vira vector(dim) + índice HNSW
-- ============================================================================


PRAGMA foreign_keys = ON;



CREATE TABLE especialidades (
    id   INTEGER PRIMARY KEY,
    nome TEXT NOT NULL UNIQUE
);



CREATE TABLE condicoes (
    id   INTEGER PRIMARY KEY,
    nome TEXT NOT NULL UNIQUE
);



CREATE TABLE tipos_questao (
    id   INTEGER PRIMARY KEY,
    nome TEXT NOT NULL UNIQUE
);



CREATE TABLE profissionais (
    id                       INTEGER PRIMARY KEY,
    nome                     TEXT    NOT NULL,
    registro_conselho        TEXT    NOT NULL UNIQUE,
    especialidade_principal_id INTEGER NOT NULL REFERENCES especialidades(id),
    criado_em                DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);



CREATE TABLE profissional_especialidade (
    profissional_id  INTEGER NOT NULL REFERENCES profissionais(id) ON DELETE CASCADE,
    especialidade_id INTEGER NOT NULL REFERENCES especialidades(id),
    PRIMARY KEY (profissional_id, especialidade_id)
);



CREATE TABLE pacientes (
    id              INTEGER PRIMARY KEY,
    nome            TEXT    NOT NULL,
    cpf_mascarado   TEXT    NOT NULL UNIQUE,
    data_nascimento DATE    NOT NULL,
    sexo            TEXT    NOT NULL CONSTRAINT ck_pacientes_sexo CHECK (sexo IN ('M', 'F')),
    telefone_mock   TEXT    NOT NULL,
    criado_em       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);



CREATE TABLE paciente_condicao (
    paciente_id      INTEGER NOT NULL REFERENCES pacientes(id) ON DELETE CASCADE,
    condicao_id      INTEGER NOT NULL REFERENCES condicoes(id),
    data_diagnostico DATE    NOT NULL,
    status           TEXT    NOT NULL
        CONSTRAINT ck_paciente_condicao_status CHECK (status IN ('ativo', 'cronico', 'resolvido')),
    PRIMARY KEY (paciente_id, condicao_id)
);

CREATE INDEX ix_paciente_condicao_condicao ON paciente_condicao(condicao_id);



CREATE TABLE atendimentos (
    id               INTEGER PRIMARY KEY,
    dataset_ref      INTEGER  NOT NULL UNIQUE,
    paciente_id      INTEGER  NOT NULL REFERENCES pacientes(id),
    profissional_id  INTEGER  NOT NULL REFERENCES profissionais(id),
    condicao_id      INTEGER  NOT NULL REFERENCES condicoes(id),
    tipo_questao_id  INTEGER  NOT NULL REFERENCES tipos_questao(id),
    data_atendimento DATETIME NOT NULL,
    queixa           TEXT     NOT NULL,
    conduta          TEXT     NOT NULL
);

CREATE INDEX ix_atendimentos_paciente     ON atendimentos(paciente_id);
CREATE INDEX ix_atendimentos_condicao     ON atendimentos(condicao_id);
CREATE INDEX ix_atendimentos_profissional ON atendimentos(profissional_id);
CREATE INDEX ix_atendimentos_data         ON atendimentos(data_atendimento);



CREATE TABLE exames (
    id             INTEGER PRIMARY KEY,
    atendimento_id INTEGER NOT NULL REFERENCES atendimentos(id) ON DELETE CASCADE,
    nome_exame     TEXT    NOT NULL,
    data_exame     DATE    NOT NULL,
    resultado      TEXT    NOT NULL
);

CREATE INDEX ix_exames_atendimento ON exames(atendimento_id);



CREATE TABLE agendamentos (
    id                  INTEGER PRIMARY KEY,
    paciente_id         INTEGER NOT NULL REFERENCES pacientes(id),
    profissional_id     INTEGER NOT NULL REFERENCES profissionais(id),
    especialidade_id    INTEGER NOT NULL REFERENCES especialidades(id),
    data_hora_agendada  DATETIME NOT NULL,
    data_hora_realizada DATETIME,
    status              TEXT NOT NULL
        CONSTRAINT ck_agendamentos_status
        CHECK (status IN ('agendada', 'confirmada', 'realizada', 'cancelada', 'nao_compareceu')),
    motivo              TEXT,
    observacoes         TEXT,
    duracao_minutos     INTEGER NOT NULL DEFAULT 30,
    lembrete_enviado    INTEGER NOT NULL DEFAULT 0,
    recorrente          INTEGER NOT NULL DEFAULT 0,
    criado_em           DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    atualizado_em       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX ix_agendamentos_paciente     ON agendamentos(paciente_id);
CREATE INDEX ix_agendamentos_profissional ON agendamentos(profissional_id);
CREATE INDEX ix_agendamentos_especialidade ON agendamentos(especialidade_id);
CREATE INDEX ix_agendamentos_data         ON agendamentos(data_hora_agendada);
CREATE INDEX ix_agendamentos_status       ON agendamentos(status);



CREATE TABLE prontuario_chunks (
    id               INTEGER PRIMARY KEY,
    atendimento_id   INTEGER NOT NULL REFERENCES atendimentos(id) ON DELETE CASCADE,
    ordem_chunk      INTEGER NOT NULL,
    conteudo         TEXT    NOT NULL,
    embedding        BLOB,
    modelo_embedding TEXT,
    dimensoes        INTEGER,
    UNIQUE (atendimento_id, ordem_chunk),
    CONSTRAINT ck_prontuario_chunks_embedding
        CHECK (embedding IS NULL OR (modelo_embedding IS NOT NULL AND dimensoes IS NOT NULL))
);

CREATE INDEX ix_prontuario_chunks_atendimento ON prontuario_chunks(atendimento_id);



CREATE TABLE log_auditoria (
    id        INTEGER  PRIMARY KEY,
    sessao_id TEXT     NOT NULL,
    acao      TEXT     NOT NULL,
    detalhe   TEXT     NOT NULL DEFAULT '{}'
        CONSTRAINT ck_log_auditoria_detalhe CHECK (detalhe = '{}' OR json_valid(detalhe)),
    criado_em DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX ix_log_auditoria_sessao ON log_auditoria(sessao_id);



CREATE VIRTUAL TABLE atendimentos_fts USING fts5(
    queixa,
    conduta,
    content='atendimentos',
    content_rowid='id',
    tokenize='unicode61 remove_diacritics 2'
);



CREATE VIEW vw_historico_paciente AS
SELECT
    a.id               AS atendimento_id,
    a.paciente_id,
    pa.nome            AS paciente,
    c.nome             AS condicao,
    tq.nome            AS tipo_questao,
    pr.nome            AS profissional,
    e.nome             AS especialidade_principal,
    a.data_atendimento,
    a.queixa,
    a.conduta
FROM atendimentos a
JOIN pacientes     pa ON pa.id = a.paciente_id
JOIN condicoes     c  ON c.id  = a.condicao_id
JOIN tipos_questao tq ON tq.id = a.tipo_questao_id
JOIN profissionais pr ON pr.id = a.profissional_id
JOIN especialidades e ON e.id = pr.especialidade_principal_id;



CREATE VIEW vw_exames_paciente AS
SELECT
    e.id             AS exame_id,
    e.atendimento_id,
    a.paciente_id,
    e.nome_exame,
    e.data_exame,
    e.resultado
FROM exames e
JOIN atendimentos a ON a.id = e.atendimento_id;



CREATE VIEW vw_estatisticas_base AS
SELECT
    (SELECT COUNT(*) FROM pacientes)         AS pacientes,
    (SELECT COUNT(*) FROM profissionais)     AS profissionais,
    (SELECT COUNT(*) FROM atendimentos)      AS atendimentos,
    (SELECT COUNT(*) FROM condicoes)         AS condicoes,
    (SELECT COUNT(*) FROM especialidades)    AS especialidades,
    (SELECT COUNT(*) FROM exames)            AS exames,
    (SELECT COUNT(*) FROM log_auditoria)     AS logs_auditoria,
    (SELECT COUNT(*) FROM agendamentos)      AS agendamentos;


