CREATE TABLE pacientes (
    id              INTEGER PRIMARY KEY,
    nome            TEXT    NOT NULL,
    cpf_mascarado   TEXT    NOT NULL UNIQUE,
    data_nascimento DATE    NOT NULL,
    sexo            TEXT    NOT NULL CONSTRAINT ck_pacientes_sexo CHECK (sexo IN ('M', 'F')),
    telefone_mock   TEXT    NOT NULL,
    criado_em       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);
