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
