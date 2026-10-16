-- Permisos del rol de solo lectura sobre el dominio (T2.2, R-3.5, D14, D65).
--
-- Se aplica DESPUÉS de crear o restaurar el esquema, porque las tablas llegan con él. Es idempotente y
-- tolera tablas que todavía no existen (avisa y sigue).
--
-- `agent_runs` queda fuera a propósito (D21): la trazabilidad no se concede a este rol.
-- `documentos` y `documentos_chunks` entran: la herramienta de RAG las lee con este rol por una vía propia;
-- la whitelist de la herramienta SQL las excluye (D21), así que el agente no puede consultarlas con SQL.

DO $$
DECLARE
    t text;
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'agent_ro') THEN
        RAISE NOTICE 'el rol agent_ro no existe: no se concedió nada';
        RETURN;
    END IF;

    GRANT USAGE ON SCHEMA public TO agent_ro;

    FOREACH t IN ARRAY ARRAY[
        'autores', 'editoriales', 'categorias', 'libros', 'libros_autores', 'socios', 'prestamos',
        'v_prestamos_estado', 'documentos', 'documentos_chunks'
    ] LOOP
        IF to_regclass('public.' || t) IS NOT NULL THEN
            EXECUTE format('GRANT SELECT ON public.%I TO agent_ro', t);
        ELSE
            RAISE NOTICE 'public.% no existe todavía', t;
        END IF;
    END LOOP;
END
$$;

-- Defensa en profundidad: aunque alguien le concediera permisos de escritura, la sesión es de lectura.
ALTER ROLE agent_ro SET default_transaction_read_only = on;
