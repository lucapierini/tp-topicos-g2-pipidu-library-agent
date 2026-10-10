-- Trazabilidad de ejecución (T7.4, R-6.1 a R-6.5, Art. 5).
--
-- Una fila por consulta procesada, resuelta o no. Idempotente: se puede aplicar sobre una base
-- recién creada, sobre una restauración del dump y sobre la base compartida sin duplicar nada.
--
-- Qué NO hace: no concede nada a `agent_ro`. La herramienta SQL no lee `agent_runs` (D21): si pudiera,
-- un usuario reconstruiría la historia de consultas de los demás.

CREATE TABLE IF NOT EXISTS agent_runs (
    id             BIGSERIAL    PRIMARY KEY,
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT now(),         -- R-6.1: timestamp
    question       TEXT         NOT NULL,                       -- R-6.1: pregunta
    classification TEXT         NOT NULL
                   CHECK (classification IN ('sql', 'rag', 'hybrid', 'none')),  -- R-6.1
    status         TEXT         NOT NULL
                   CHECK (status IN ('ok', 'no_coverage', 'error')),            -- R-6.3
    sources        TEXT[]       NOT NULL DEFAULT '{}',          -- fuentes efectivamente invocadas
    tools          TEXT[]       NOT NULL DEFAULT '{}',          -- R-6.1: herramientas invocadas, en orden
    generated_sql  TEXT,                                        -- R-6.1: sentencia como la generó el modelo
    executed_sql   TEXT,                                        -- R-3.9: sentencia normalizada que corrió
    chunks         JSONB        NOT NULL DEFAULT '[]'::jsonb,   -- R-6.1: fragmentos recuperados
    answer         TEXT         NOT NULL,                       -- R-6.1: respuesta
    latency_ms     INTEGER      NOT NULL CHECK (latency_ms >= 0),               -- R-6.1: latencia total
    attempts       JSONB        NOT NULL DEFAULT '[]'::jsonb,   -- R-6.4: intentos de generación y su resultado
    error_code     TEXT,                                        -- R-6.3: motivo del rechazo o fallo
    error_detail   TEXT,
    model_id       TEXT         NOT NULL,                       -- R-6.5: modelo que resolvió la consulta
    endpoint       TEXT         NOT NULL CHECK (endpoint IN ('local', 'api')),  -- R-6.5
    trace          JSONB        NOT NULL DEFAULT '[]'::jsonb    -- orden de eventos: la clasificación va primero
);

COMMENT ON TABLE agent_runs IS 'Registro de cada consulta del agente (R-6.x). La herramienta SQL no la lee (D21).';
COMMENT ON COLUMN agent_runs.endpoint IS 'local: modelo en la máquina del desarrollador; api: proveedor externo. Una corrida local no es evidencia de aceptación (R-2.8).';

CREATE INDEX IF NOT EXISTS agent_runs_created_at_idx ON agent_runs (created_at DESC);
CREATE INDEX IF NOT EXISTS agent_runs_classification_idx ON agent_runs (classification, status);

-- El rol que escribe el registro solo puede insertar. `RETURNING id` exige poder leer esa columna.
-- Se concede únicamente si el rol existe (en la base compartida lo crea quien administra).
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'agent_logger') THEN
        GRANT USAGE ON SCHEMA public TO agent_logger;
        GRANT INSERT ON agent_runs TO agent_logger;
        GRANT SELECT (id) ON agent_runs TO agent_logger;
        GRANT USAGE ON SEQUENCE agent_runs_id_seq TO agent_logger;
    ELSE
        RAISE NOTICE 'el rol agent_logger no existe: no se concedieron permisos sobre agent_runs';
    END IF;
END
$$;
