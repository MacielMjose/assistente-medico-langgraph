CREATE TABLE paciente_condicao (
    paciente_id      INTEGER NOT NULL REFERENCES pacientes(id) ON DELETE CASCADE,
    condicao_id      INTEGER NOT NULL REFERENCES condicoes(id),
    data_diagnostico DATE NOT NULL,
    status           TEXT NOT NULL
        CONSTRAINT ck_paciente_condicao_status CHECK (status IN ('ativo', 'cronico', 'resolvido')),
    PRIMARY KEY (paciente_id, condicao_id)
);

CREATE INDEX ix_paciente_condicao_condicao ON paciente_condicao(condicao_id);
