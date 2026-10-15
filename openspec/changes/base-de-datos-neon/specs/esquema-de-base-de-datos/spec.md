# Spec Delta

## Purpose

Define la forma del esquema relacional y del almacén vectorial en PostgreSQL (Neon), de modo que el
SQL que genera el agente sea simple, seguro y no dependa de la fecha de ejecución.

## ADDED Requirements

### Requirement: R-7.1 — Base única en Neon con pgvector
El sistema SHALL mantener el dominio relacional y el almacén vectorial en la misma base PostgreSQL de
Neon, con la extensión `vector` habilitada.

#### Scenario: base completa
- **GIVEN** el esquema aplicado en la rama `production` del proyecto `library-agent`
- **WHEN** se inspeccionan los objetos de la base
- **THEN** existen 9 tablas (7 de dominio: `autores`, `categorias`, `editoriales`, `libros`, `libros_autores`, `socios`, `prestamos`; 2 documentales: `documentos`, `documentos_chunks`) y la vista `v_prestamos_estado`
- **AND** la extensión `vector` está instalada

### Requirement: R-7.2 — Identificadores generados por la base
Toda clave primaria sintética SHALL usar `GENERATED ALWAYS AS IDENTITY`.

#### Scenario: id manual rechazado
- **WHEN** se intenta insertar un `id` explícito en una tabla de dominio
- **THEN** PostgreSQL rechaza la inserción

### Requirement: R-7.3 — Libros con varios autores
Un libro SHALL poder tener uno o más autores mediante la tabla puente `libros_autores`, y `libros` MUST NOT tener columna `autor_id`.

#### Scenario: libro de dos autores
- **GIVEN** un libro con dos filas en `libros_autores`
- **WHEN** se consultan sus autores por `orden`
- **THEN** se obtienen ambos, en el orden de portada

### Requirement: R-7.4 — Estado de préstamo consistente
`prestamos.estado` SHALL valer solo `activo` o `devuelto`, y MUST ser `devuelto` si y solo si `fecha_devolucion_real` no es nula.

#### Scenario: estado incoherente
- **WHEN** se inserta un préstamo `activo` con `fecha_devolucion_real` cargada
- **THEN** PostgreSQL rechaza la fila por el CHECK `prestamos_estado_real_ck`

#### Scenario: valor no permitido
- **WHEN** se inserta un préstamo con `estado = 'vencido'`
- **THEN** PostgreSQL rechaza la fila

### Requirement: R-7.5 — Vencimiento calculado
El esquema SHALL exponer la vista `v_prestamos_estado` con `estado_calculado` y `dias_atraso`, derivados de la fecha actual.

#### Scenario: préstamo vencido
- **GIVEN** un préstamo activo cuya `fecha_devolucion_prevista` pasó hace 3 días
- **WHEN** se consulta `v_prestamos_estado`
- **THEN** `estado_calculado` es `vencido`
- **AND** `dias_atraso` es 3

### Requirement: R-7.6 — Ejemplares acotados
`libros.ejemplares_disponibles` SHALL estar entre 0 y `ejemplares_totales`.

#### Scenario: disponibles mayores a totales
- **WHEN** se intenta guardar `ejemplares_disponibles > ejemplares_totales`
- **THEN** PostgreSQL rechaza la fila por `libros_disponibles_ck`

### Requirement: R-7.7 — Borrado protegido
Las referencias de dominio SHALL usar `ON DELETE RESTRICT`; las de la tabla puente y de `documentos_chunks`, `ON DELETE CASCADE`.

#### Scenario: libro con préstamos
- **GIVEN** un libro con préstamos registrados
- **WHEN** se intenta borrarlo
- **THEN** PostgreSQL rechaza el borrado

#### Scenario: documento con fragmentos
- **WHEN** se borra un documento
- **THEN** se eliminan sus fragmentos

### Requirement: R-7.8 — Vector de 768 dimensiones con índice por coseno
`documentos_chunks.embedding` SHALL ser `vector(768)` con un índice HNSW `vector_cosine_ops`.

#### Scenario: dimensión incorrecta
- **WHEN** se inserta un vector de otra dimensión
- **THEN** PostgreSQL rechaza la fila

#### Scenario: el índice se usa para coseno
- **WHEN** se inspecciona el índice de `documentos_chunks`
- **THEN** declara el operador `vector_cosine_ops` (y no L2 por defecto)

### Requirement: R-7.9 — El SQL tool no accede al almacén vectorial
El rol que ejecuta el SQL generado por el agente SHALL poder leer solo las tablas de negocio y la vista, y MUST NOT poder escribir ni leer `documentos` ni `documentos_chunks`.

#### Scenario: lectura de chunks por el SQL tool
- **GIVEN** la conexión del rol de solo lectura del SQL tool
- **WHEN** consulta `documentos_chunks`
- **THEN** PostgreSQL rechaza la consulta por permisos

#### Scenario: escritura
- **WHEN** ese rol intenta `INSERT`, `UPDATE`, `DELETE` o DDL
- **THEN** PostgreSQL lo rechaza

### Requirement: R-7.10 — Reglas de negocio fuera de las tablas
El esquema MUST NOT almacenar plazos, límites de préstamo ni importes de multa.

#### Scenario: ausencia de columnas de política
- **WHEN** se revisa el DDL
- **THEN** no hay tabla ni columna que contenga plazo en días, máximo de libros ni monto de multa
