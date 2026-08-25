CREATE VIRTUAL TABLE atendimentos_fts USING fts5(
    queixa,
    conduta,
    content='atendimentos',
    content_rowid='id',
    tokenize='unicode61 remove_diacritics 2'
);
