CREATE TABLE exames (
    id             INTEGER PRIMARY KEY,
    atendimento_id INTEGER NOT NULL REFERENCES atendimentos(id) ON DELETE CASCADE,
    nome_exame     TEXT    NOT NULL,
    data_exame     DATE    NOT NULL,
    resultado      TEXT    NOT NULL
);

CREATE INDEX ix_exames_atendimento ON exames(atendimento_id);
