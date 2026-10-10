# Spec Delta

## Purpose

Define el comportamiento de la herramienta que traduce una consulta en lenguaje natural a una
sentencia SQL, la valida antes de ejecutarla y devuelve el resultado con la sentencia ejecutada.

## ADDED Requirements

### Requirement: R-3.1 — El agente genera la sentencia, la herramienta solo valida y ejecuta
El agente SHALL generar una única sentencia `SELECT` a partir de la consulta en lenguaje natural y
entregarla a la herramienta ya formada. La herramienta SHALL NO invocar el modelo.

#### Scenario: traducción correcta
- **WHEN** la consulta "¿Cuáles son los 5 libros más prestados este cuatrimestre?" se traduce a SQL
- **THEN** se produce una única sentencia
- **AND** la sentencia devuelve el ranking esperado

#### Scenario: la herramienta no llama al modelo
- **GIVEN** una sentencia recibida por la herramienta
- **WHEN** la herramienta la valida y ejecuta
- **THEN** no se realiza ninguna llamada adicional al modelo
- **AND** la herramienta puede ejecutarse sin credenciales de API

### Requirement: R-3.2 — Restricción a sentencias de lectura
La herramienta SHALL rechazar cualquier sentencia que no comience con `SELECT` o `WITH`, y SHALL
rechazar cláusulas de bloqueo como `FOR UPDATE`, que no son lectura.

#### Scenario: sentencia destructiva
- **GIVEN** una sentencia generada que contiene `DELETE FROM prestamos WHERE socio_id = 1`
- **WHEN** la herramienta evalúa la sentencia
- **THEN** rechaza la ejecución
- **AND** devuelve el error `SQL_NOT_READONLY`
- **AND** la base de datos no recibe ninguna consulta

#### Scenario: bloqueo de fila
- **GIVEN** la sentencia `SELECT id FROM libros FOR UPDATE`
- **WHEN** la herramienta evalúa la sentencia
- **THEN** rechaza la ejecución
- **AND** devuelve el error `SQL_NOT_READONLY`

### Requirement: R-3.3 — Rechazo de múltiples statements y comentarios
La herramienta SHALL rechazar sentencias que contengan `;`, comentarios `--` o `/*`, o instrucciones
`INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `CREATE`, `TRUNCATE`, `GRANT`, `COPY`, `CALL` o `EXEC`.

#### Scenario: inyección por statement múltiple
- **GIVEN** la sentencia `SELECT 1; DROP TABLE libros`
- **WHEN** la herramienta evalúa la sentencia
- **THEN** rechaza la ejecución
- **AND** devuelve el error `SQL_NOT_READONLY`

#### Scenario: comentario embebido
- **GIVEN** la sentencia `SELECT * FROM libros -- comentario`
- **WHEN** la herramienta evalúa la sentencia
- **THEN** rechaza la ejecución
- **AND** devuelve el error `SQL_NOT_READONLY`

#### Scenario: parse estricto
- **GIVEN** una sentencia mal formada
- **WHEN** el parser no puede interpretarla
- **THEN** la validación falla con `SQL_NOT_READONLY`
- **AND** no se degrada a una interpretación genérica tipo `Command`

### Requirement: R-3.4 — Whitelist de tablas y columnas
La herramienta SHALL rechazar referencias a tablas o columnas fuera de la whitelist del esquema
documentado (las funciones se rigen por R-3.13). La whitelist cubre el modelo completo del dominio
(Art. 11): no oculta columnas por política de privacidad, es un control de alcance y de inyección.

#### Scenario: tabla del catálogo interno
- **GIVEN** una sentencia que referencia `pg_catalog.pg_tables`
- **WHEN** la herramienta evalúa la sentencia
- **THEN** rechaza la ejecución
- **AND** devuelve el error `TABLE_NOT_ALLOWED`

#### Scenario: columna fuera de la whitelist
- **GIVEN** una sentencia que referencia una columna no documentada
- **WHEN** la herramienta evalúa la sentencia
- **THEN** rechaza la ejecución
- **AND** devuelve el error `COLUMN_NOT_ALLOWED`

### Requirement: R-3.14 — Expansión de `SELECT *`
La herramienta SHALL expandir `SELECT *` a las columnas de la whitelist antes de ejecutar, de modo que
una columna física del esquema fuera de la whitelist sea inalcanzable.

#### Scenario: `SELECT *` no evade la whitelist de columnas
- **GIVEN** la sentencia `SELECT * FROM socios` y una columna física del esquema fuera de la whitelist
- **WHEN** la herramienta evalúa la sentencia
- **THEN** la sentencia ejecutada es la expandida a las columnas de la whitelist
- **AND** la columna no documentada no aparece en el resultado

### Requirement: R-3.15 — Normalización de identificadores
La herramienta SHALL normalizar los identificadores a minúsculas antes de aplicar la whitelist y SHALL
preservar los literales de texto sin modificación.

#### Scenario: identificador entre comillas
- **GIVEN** la sentencia `SELECT id FROM "Libros"`
- **WHEN** la herramienta evalúa la sentencia
- **THEN** normaliza el identificador a minúsculas y lo acepta

#### Scenario: literal preservado
- **GIVEN** la sentencia `SELECT titulo FROM libros WHERE titulo = 'Cien años de soledad'`
- **WHEN** se genera la sentencia normalizada
- **THEN** el literal permanece idéntico
- **AND** los valores citados en la respuesta coinciden con los valores devueltos (Art. 4)

#### Scenario: tabla inexistente
- **GIVEN** una sentencia que referencia una tabla no incluida en la whitelist
- **WHEN** la herramienta evalúa la sentencia
- **THEN** rechaza la ejecución
- **AND** devuelve el error `TABLE_NOT_ALLOWED`

### Requirement: R-3.5 — Ejecución con rol de solo lectura
La herramienta SHALL ejecutar las sentencias válidas contra la base usando un rol de solo lectura.

#### Scenario: ejecución válida
- **GIVEN** una sentencia que pasó la validación estática
- **WHEN** se ejecuta contra la base
- **THEN** la conexión utiliza el rol de solo lectura
- **AND** devuelve las filas esperadas

### Requirement: R-3.6 — Límite de filas y timeout
La herramienta SHALL aplicar un límite máximo de 50 filas devueltas y un timeout de ejecución de 10 segundos.

#### Scenario: resultado excesivo
- **GIVEN** una sentencia con `LIMIT 100000`
- **WHEN** se ejecuta
- **THEN** la herramienta devuelve como máximo 50 filas

#### Scenario: timeout de ejecución
- **GIVEN** una sentencia que supera los 10 segundos de ejecución
- **WHEN** se alcanza el límite
- **THEN** la herramienta devuelve el error `TIMEOUT`

### Requirement: R-3.7 — Validación previa a la ejecución
La herramienta SHALL devolver un error tipado ante una validación fallida y NO ejecutar la sentencia.

#### Scenario: validación fallida
- **GIVEN** una sentencia rechazada por la validación estática
- **WHEN** la herramienta procesa la sentencia
- **THEN** no se establece conexión de ejecución
- **AND** el registro de ejecución consigna el motivo del rechazo

### Requirement: R-3.8 — Reporte de resultado vacío
La herramienta SHALL reportar "sin resultados" cuando la sentencia no devuelve filas, sin interpretar ni inferir.

#### Scenario: socio sin préstamos
- **GIVEN** un socio sin préstamos registrados
- **WHEN** la consulta devuelve 0 filas
- **THEN** la herramienta reporta "sin resultados"
- **AND** la respuesta final no afirma hechos no presentes en el resultado

### Requirement: R-3.9 — Exposición de la sentencia ejecutada
La herramienta SHALL devolver la sentencia efectivamente ejecutada para exhibirla en la interfaz. Cuando
la validación normaliza la sentencia (expansión de `*`), la sentencia exhibida es la normalizada, no la
original del modelo.

#### Scenario: sentencia visible
- **WHEN** una consulta se resuelve vía SQL
- **THEN** la interfaz muestra la sentencia ejecutada
- **AND** los valores citados en la respuesta coinciden con las filas devueltas

#### Scenario: sentencia normalizada
- **GIVEN** una sentencia aceptada con `SELECT *`
- **WHEN** se registra la ejecución
- **THEN** se consigna la sentencia expandida a la whitelist
- **AND** los literales de la sentencia no se modifican por la normalización

### Requirement: R-3.10 — Regeneración limitada ante SQL rechazado
El agente SHALL poder regenerar la sentencia hasta un máximo de dos intentos cuando la validación
estática la rechaza. Si el segundo intento también es rechazado, el sistema SHALL reportar el error al usuario.

#### Scenario: primer rechazo y regeneración exitosa
- **GIVEN** un primer intento rechazado por la validación estática
- **WHEN** el agente genera una sentencia válida en el segundo intento
- **THEN** la segunda sentencia se ejecuta
- **AND** el registro consigna los dos intentos

#### Scenario: dos intentos rechazados
- **GIVEN** dos intentos consecutivos rechazados por la validación estática
- **WHEN** se alcanza el límite de intentos
- **THEN** el sistema no ejecuta ninguna sentencia
- **AND** la respuesta informa el motivo del rechazo al usuario

### Requirement: R-3.13 — Whitelist de funciones
La herramienta SHALL ejecutar únicamente funciones incluidas en una allowlist documentada (agregación,
escalares y temporales). Las funciones de efecto SHALL rechazarse antes de ejecutar, porque el timeout
limita el tiempo pero no los efectos.

#### Scenario: función de efecto
- **GIVEN** la sentencia `SELECT id, pg_sleep(10) FROM libros`
- **WHEN** la herramienta evalúa la sentencia
- **THEN** rechaza la ejecución
- **AND** devuelve el error `FUNCTION_NOT_ALLOWED`

#### Scenario: función permitida
- **GIVEN** la sentencia `SELECT count(*) AS c FROM prestamos`
- **WHEN** la herramienta evalúa la sentencia
- **THEN** la acepta

### Requirement: R-3.11 — Semántica temporal definida por configuración
El sistema SHALL resolver las expresiones temporales de las consultas usando los rangos definidos en
configuración, no una interpretación libre del modelo.

#### Scenario: rango de cuatrimestre
- **GIVEN** el rango de cuatrimestre configurado (2026-08-01 a 2026-11-30)
- **WHEN** el usuario pregunta por "este cuatrimestre"
- **THEN** la sentencia filtra por ese rango
- **AND** el mismo rango se aplica a todas las consultas del golden set

#### Scenario: días transcurridos
- **WHEN** el usuario pregunta por un préstamo "hace 20 días"
- **THEN** el cálculo se realiza sobre `CURRENT_DATE` con la zona horaria configurada

### Requirement: R-3.12 — Estado de vencimiento calculado
El estado de vencimiento de un préstamo SHALL determinarse por cálculo a partir de las fechas, no por
un valor almacenado manualmente.

#### Scenario: préstamo vencido por cálculo
- **GIVEN** un préstamo sin devolución y con fecha prevista anterior a la fecha actual
- **WHEN** se consulta qué socios tienen préstamos vencidos
- **THEN** el préstamo se reporta como vencido por cálculo
- **AND** el resultado coincide con el caso G3 del golden set

### Requirement: R-3.16 — Error de ejecución
La herramienta SHALL devolver el error tipado `EXECUTION_ERROR` cuando una sentencia válida falla al
ejecutarse, sin reinterpretar el mensaje de la base ni completar información desde fuera del resultado.

#### Scenario: fallo al ejecutar
- **GIVEN** una sentencia que pasó la validación estática y falla al ejecutarse
- **WHEN** la herramienta captura el error
- **THEN** devuelve `executed = False` con `EXECUTION_ERROR`
- **AND** no se infiere ningún hecho a partir del fallo

#### Scenario: la validación falla antes de tocar la base
- **GIVEN** una sentencia rechazada por la validación estática
- **WHEN** la herramienta la procesa
- **THEN** no se abre ninguna conexión ni se envía la sentencia
