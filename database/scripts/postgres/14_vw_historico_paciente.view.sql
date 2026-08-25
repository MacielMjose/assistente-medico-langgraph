CREATE VIEW vw_historico_paciente AS
SELECT
    a.id               AS atendimento_id,
    a.paciente_id,
    pa.nome            AS paciente,
    c.nome             AS condicao,
    tq.nome            AS tipo_questao,
    pr.nome            AS profissional,
    e.nome             AS especialidade_principal,
    a.data_atendimento,
    a.queixa,
    a.conduta
FROM atendimentos a
JOIN pacientes      pa ON pa.id = a.paciente_id
JOIN condicoes      c  ON c.id  = a.condicao_id
JOIN tipos_questao  tq ON tq.id = a.tipo_questao_id
JOIN profissionais  pr ON pr.id = a.profissional_id
JOIN especialidades e  ON e.id = pr.especialidade_principal_id;
