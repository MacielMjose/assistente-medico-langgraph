CREATE VIEW vw_exames_paciente AS
SELECT
    e.id             AS exame_id,
    e.atendimento_id,
    a.paciente_id,
    e.nome_exame,
    e.data_exame,
    e.resultado
FROM exames e
JOIN atendimentos a ON a.id = e.atendimento_id;
