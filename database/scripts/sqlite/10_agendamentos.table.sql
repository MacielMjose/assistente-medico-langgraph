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
