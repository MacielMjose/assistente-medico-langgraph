-- Sobrecarga de jsonb_path_match para compatibilidade com o PGVector (LangChain).
--
-- O langchain_community.vectorstores.PGVector gera filtros de metadados na forma
-- jsonb_path_match(cmetadata, '<caminho>', '<var_json>') com os argumentos 2 e 3
-- tipados como VARCHAR. No PostgreSQL 17 não há cast implícito de varchar para
-- jsonpath/jsonb, então registramos aqui uma sobrecarga que faz o cast explícito
-- e delega ao operador nativo.
CREATE OR REPLACE FUNCTION public.jsonb_path_match(
    alvo jsonb,
    caminho character varying,
    valor character varying
) RETURNS boolean
LANGUAGE sql
IMMUTABLE
STRICT
PARALLEL SAFE
AS $$
    SELECT pg_catalog.jsonb_path_match(alvo, caminho::jsonpath, valor::jsonb);
$$;