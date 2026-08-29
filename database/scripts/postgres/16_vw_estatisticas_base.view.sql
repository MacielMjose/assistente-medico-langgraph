CREATE VIEW vw_estatisticas_base AS
SELECT
    (SELECT COUNT(*) FROM pacientes)      AS pacientes,
    (SELECT COUNT(*) FROM profissionais)  AS profissionais,
    (SELECT COUNT(*) FROM atendimentos)   AS atendimentos,
    (SELECT COUNT(*) FROM condicoes)      AS condicoes,
    (SELECT COUNT(*) FROM especialidades) AS especialidades,
    (SELECT COUNT(*) FROM exames)         AS exames,
    (SELECT COUNT(*) FROM log_auditoria)  AS logs_auditoria,
    (SELECT COUNT(*) FROM agendamentos)   AS agendamentos;
