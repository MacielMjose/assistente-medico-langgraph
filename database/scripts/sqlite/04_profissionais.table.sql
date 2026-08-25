CREATE TABLE profissionais (
    id                       INTEGER PRIMARY KEY,
    nome                     TEXT    NOT NULL,
    registro_conselho        TEXT    NOT NULL UNIQUE,
    especialidade_principal_id INTEGER NOT NULL REFERENCES especialidades(id),
    criado_em                DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);
