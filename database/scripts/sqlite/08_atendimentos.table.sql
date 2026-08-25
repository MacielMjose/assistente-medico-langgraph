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
