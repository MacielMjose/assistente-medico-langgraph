CREATE TABLE log_auditoria (
    id        INTEGER  PRIMARY KEY,
    sessao_id TEXT     NOT NULL,
    acao      TEXT     NOT NULL,
    detalhe   TEXT     NOT NULL DEFAULT '{}'
        CONSTRAINT ck_log_auditoria_detalhe CHECK (detalhe = '{}' OR json_valid(detalhe)),
    criado_em DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX ix_log_auditoria_sessao ON log_auditoria(sessao_id);
