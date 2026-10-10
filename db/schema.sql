-- Esquema de la base de la biblioteca (T2.1). Fuente: el esquema compartido en Neon, normalizado para
-- que corra tal cual en PostgreSQL local.
--
-- Qué se cambió respecto del DDL exportado de Neon (y por qué), para que quien mantiene el esquema
-- compartido pueda reflejarlo:
--   * `CREATE SCHEMA "public"` se omite: el esquema ya existe.
--   * Se agrega `CREATE EXTENSION vector` (el DDL exportado no lo incluye y `vector(768)` lo necesita).
--   * `CREATE VIEW ... TABLESPACE public` no es sintaxis válida: se quitó `TABLESPACE public`.
--   * Se quitaron los `CREATE UNIQUE INDEX` que duplican el índice que ya crea cada PRIMARY KEY o
--     UNIQUE (`*_pkey`, `*_key`, `autores_nombre_uk`, `documentos_chunks_uk`): fallaban con
--     "relation already exists".
--   * El índice HNSW se declara con `vector_cosine_ops`. El exportado no declaraba operador y por
--     defecto pgvector usa distancia L2: el agente consulta por coseno (`<=>`, D13) y no lo usaría.
--
-- Estado de vencimiento (D7): la tabla guarda solo `activo`/`devuelto`; "vencido" se calcula en la vista
-- `v_prestamos_estado.estado_calculado`.

CREATE EXTENSION IF NOT EXISTS vector;

-- ---------------------------------------------------------------- dominio

CREATE TABLE autores (
  id               integer PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
  nombre           varchar(100) NOT NULL,
  apellido         varchar(100) NOT NULL,
  nacionalidad     varchar(50),
  fecha_nacimiento date,
  CONSTRAINT autores_nombre_uk UNIQUE (nombre, apellido)
);

CREATE TABLE categorias (
  id          integer PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
  nombre      varchar(80) NOT NULL CONSTRAINT categorias_nombre_key UNIQUE,
  descripcion text
);

CREATE TABLE editoriales (
  id     integer PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
  nombre varchar(100) NOT NULL CONSTRAINT editoriales_nombre_key UNIQUE,
  pais   varchar(50)
);

CREATE TABLE libros (
  id                     integer PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
  titulo                 varchar(200) NOT NULL,
  isbn                   varchar(20) NOT NULL CONSTRAINT libros_isbn_key UNIQUE,
  editorial_id           integer NOT NULL,
  categoria_id           integer NOT NULL,
  anio_publicacion       integer,
  ejemplares_totales     integer NOT NULL DEFAULT 1,
  ejemplares_disponibles integer NOT NULL DEFAULT 1,
  CONSTRAINT libros_anio_ck CHECK (anio_publicacion >= 1400 AND anio_publicacion <= 2100),
  CONSTRAINT libros_disponibles_ck CHECK (ejemplares_disponibles >= 0 AND ejemplares_disponibles <= ejemplares_totales),
  CONSTRAINT libros_totales_ck CHECK (ejemplares_totales >= 0)
);

-- Un libro puede tener varios autores (`orden` es la posición en la portada).
CREATE TABLE libros_autores (
  libro_id integer,
  autor_id integer,
  orden    smallint NOT NULL DEFAULT 1,
  CONSTRAINT libros_autores_pkey PRIMARY KEY (libro_id, autor_id)
);

CREATE TABLE socios (
  id         integer PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
  nombre     varchar(100) NOT NULL,
  apellido   varchar(100) NOT NULL,
  legajo     varchar(20) NOT NULL CONSTRAINT socios_legajo_key UNIQUE,
  tipo_socio varchar(20) NOT NULL,
  email      varchar(100) NOT NULL CONSTRAINT socios_email_key UNIQUE,
  fecha_alta date NOT NULL DEFAULT CURRENT_DATE,
  CONSTRAINT socios_tipo_ck CHECK (tipo_socio IN ('alumno', 'docente'))
);

CREATE TABLE prestamos (
  id                        integer PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
  libro_id                  integer NOT NULL,
  socio_id                  integer NOT NULL,
  fecha_prestamo            date NOT NULL,
  fecha_devolucion_prevista date NOT NULL,
  fecha_devolucion_real     date,
  estado                    varchar(20) NOT NULL DEFAULT 'activo',
  CONSTRAINT prestamos_estado_ck CHECK (estado IN ('activo', 'devuelto')),
  CONSTRAINT prestamos_estado_real_ck CHECK ((estado = 'devuelto') = (fecha_devolucion_real IS NOT NULL)),
  CONSTRAINT prestamos_fechas_ck CHECK (fecha_devolucion_prevista >= fecha_prestamo),
  CONSTRAINT prestamos_real_ck CHECK (fecha_devolucion_real IS NULL OR fecha_devolucion_real >= fecha_prestamo)
);

-- ---------------------------------------------------------------- repositorio documental (RAG)

CREATE TABLE documentos (
  id             integer PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
  nombre_archivo varchar(200) NOT NULL CONSTRAINT documentos_nombre_archivo_key UNIQUE,
  tipo           varchar(30) NOT NULL,
  bucket_key     varchar(300),
  sha256         char(64),
  creado_en      timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT documentos_tipo_ck CHECK (tipo IN ('reglamento', 'manual', 'politica', 'resena'))
);

CREATE TABLE documentos_chunks (
  id           bigint PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
  documento_id integer NOT NULL,
  chunk_index  integer NOT NULL,
  contenido    text NOT NULL,
  embedding    vector(768) NOT NULL,
  metadata     jsonb NOT NULL DEFAULT '{}',
  CONSTRAINT documentos_chunks_uk UNIQUE (documento_id, chunk_index)
);

-- ---------------------------------------------------------------- claves foráneas

ALTER TABLE documentos_chunks ADD CONSTRAINT documentos_chunks_documento_id_fkey
  FOREIGN KEY (documento_id) REFERENCES documentos (id) ON DELETE CASCADE;
ALTER TABLE libros ADD CONSTRAINT libros_categoria_id_fkey
  FOREIGN KEY (categoria_id) REFERENCES categorias (id) ON DELETE RESTRICT;
ALTER TABLE libros ADD CONSTRAINT libros_editorial_id_fkey
  FOREIGN KEY (editorial_id) REFERENCES editoriales (id) ON DELETE RESTRICT;
ALTER TABLE libros_autores ADD CONSTRAINT libros_autores_autor_id_fkey
  FOREIGN KEY (autor_id) REFERENCES autores (id) ON DELETE RESTRICT;
ALTER TABLE libros_autores ADD CONSTRAINT libros_autores_libro_id_fkey
  FOREIGN KEY (libro_id) REFERENCES libros (id) ON DELETE CASCADE;
ALTER TABLE prestamos ADD CONSTRAINT prestamos_libro_id_fkey
  FOREIGN KEY (libro_id) REFERENCES libros (id) ON DELETE RESTRICT;
ALTER TABLE prestamos ADD CONSTRAINT prestamos_socio_id_fkey
  FOREIGN KEY (socio_id) REFERENCES socios (id) ON DELETE RESTRICT;

-- ---------------------------------------------------------------- índices (los de PK/UNIQUE ya existen)

CREATE INDEX documentos_chunks_embedding_idx ON documentos_chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX libros_categoria_idx ON libros (categoria_id);
CREATE INDEX libros_editorial_idx ON libros (editorial_id);
CREATE INDEX libros_autores_autor_idx ON libros_autores (autor_id);
CREATE INDEX prestamos_activos_idx ON prestamos (fecha_devolucion_prevista);
CREATE INDEX prestamos_libro_idx ON prestamos (libro_id);
CREATE INDEX prestamos_socio_idx ON prestamos (socio_id);

-- ---------------------------------------------------------------- vista de estado calculado (D7)

CREATE VIEW v_prestamos_estado AS
SELECT
  id, libro_id, socio_id, fecha_prestamo, fecha_devolucion_prevista, fecha_devolucion_real, estado,
  CASE
    WHEN estado = 'devuelto' THEN 'devuelto'
    WHEN fecha_devolucion_prevista < CURRENT_DATE THEN 'vencido'
    ELSE 'activo'
  END AS estado_calculado,
  CASE
    WHEN estado = 'activo' AND fecha_devolucion_prevista < CURRENT_DATE
      THEN CURRENT_DATE - fecha_devolucion_prevista
    WHEN estado = 'devuelto' AND fecha_devolucion_real > fecha_devolucion_prevista
      THEN fecha_devolucion_real - fecha_devolucion_prevista
    ELSE 0
  END AS dias_atraso
FROM prestamos p;
