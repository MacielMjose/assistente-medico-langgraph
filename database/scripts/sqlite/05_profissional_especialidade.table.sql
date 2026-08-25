CREATE TABLE profissional_especialidade (
    profissional_id  INTEGER NOT NULL REFERENCES profissionais(id) ON DELETE CASCADE,
    especialidade_id INTEGER NOT NULL REFERENCES especialidades(id),
    PRIMARY KEY (profissional_id, especialidade_id)
);
