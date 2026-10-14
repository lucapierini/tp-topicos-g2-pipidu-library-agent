# Spec Delta

## Purpose

Define la interfaz web con la que una persona consulta al agente de la biblioteca: qué ve mientras la
consulta está en curso, cómo se presenta la respuesta con su fuente y su evidencia, y cómo se levanta junto
con el resto del sistema en el entorno local (D81).

## ADDED Requirements

### Requirement: R-8.1 — Envío de una consulta
La interfaz SHALL permitir escribir una consulta en lenguaje natural y enviarla a `POST /ask` de la API.
SHALL NO enviar una consulta vacía o de solo espacios, y SHALL NO enviar una nueva mientras otra esté en curso.

#### Scenario: consulta válida
- **GIVEN** texto escrito en el campo de consulta
- **WHEN** la persona la envía
- **THEN** la interfaz llama a `POST /ask` con `{"question": "<texto>"}`
- **AND** pasa al estado "en curso"

#### Scenario: consulta vacía
- **GIVEN** el campo de consulta vacío o con solo espacios
- **WHEN** la persona intenta enviarla
- **THEN** no se hace ninguna llamada a la API

#### Scenario: consulta en curso
- **GIVEN** una consulta en curso
- **WHEN** la persona intenta enviar otra
- **THEN** el envío está deshabilitado hasta que la primera termine o se cancele

### Requirement: R-8.2 — Progreso en vivo
Mientras la consulta está en curso, la interfaz SHALL mostrar el progreso real a medida que llegan los
eventos `classified`, `tool_call`, `tool_result`, `step`, `composing` y `heartbeat`. SHALL NO presentar
ninguna fuente como respuesta antes del evento `result` (R-7.2, Art. 4).

#### Scenario: eventos de progreso
- **WHEN** llegan `classified` y `tool_call` antes de `result`
- **THEN** la interfaz muestra la clasificación y la herramienta invocada
- **AND** no muestra todavía ninguna fuente como declarada

#### Scenario: espera larga
- **GIVEN** una consulta que tarda más de 5 segundos sin eventos de progreso
- **WHEN** llega un `heartbeat`
- **THEN** la interfaz muestra los segundos transcurridos y sigue en curso

### Requirement: R-8.3 — Respuesta con proveniencia
Al recibir `result`, la interfaz SHALL mostrar `answer`, las `sources` declaradas y el `answer_kind`.
Una respuesta con `answer_kind` `no_coverage` o `error` SHALL distinguirse visualmente de una `answer`
y SHALL NO presentarse como una respuesta con fuente.

#### Scenario: respuesta con fuente
- **GIVEN** un `result` con `answer_kind` `answer` y `sources` no vacío
- **WHEN** la interfaz lo recibe
- **THEN** muestra el texto de la respuesta
- **AND** muestra cada fuente declarada

#### Scenario: sin cobertura
- **GIVEN** un `result` con `answer_kind` `no_coverage`
- **WHEN** la interfaz lo recibe
- **THEN** lo presenta como ausencia de información, no como una respuesta con fuente

#### Scenario: error del agente
- **GIVEN** un `result` con `answer_kind` `error`, o un evento `error`
- **WHEN** la interfaz lo recibe
- **THEN** muestra el error y permite reintentar

### Requirement: R-8.4 — Evidencia consultable
La interfaz SHALL permitir ver la evidencia del `result`: la sentencia SQL ejecutada y sus filas, y los
fragmentos citados con su documento y ubicación. Los valores SHALL mostrarse tal como llegan, sin
reinterpretarlos.

#### Scenario: evidencia SQL
- **GIVEN** un `result` con `evidence.sql` y `evidence.rows`
- **WHEN** la persona abre la evidencia
- **THEN** ve la sentencia y las filas en una tabla

#### Scenario: evidencia documental
- **GIVEN** un `result` con `evidence.chunks`
- **WHEN** la persona abre la evidencia
- **THEN** ve cada fragmento con su `document` y su `location`

#### Scenario: sin evidencia
- **GIVEN** un `result` sin evidencia
- **WHEN** la interfaz lo muestra
- **THEN** no ofrece una sección de evidencia vacía

### Requirement: R-8.5 — Cancelación
La interfaz SHALL permitir cancelar una consulta en curso cortando la conexión, de modo que la API
cancele al agente (R-7.5). Tras cancelar, SHALL volver al estado inicial sin mostrar una respuesta parcial.

#### Scenario: cancelar
- **GIVEN** una consulta en curso
- **WHEN** la persona la cancela
- **THEN** la interfaz corta la conexión con la API
- **AND** vuelve a permitir enviar una consulta nueva
- **AND** no muestra respuesta ni fuentes de la consulta cancelada

### Requirement: R-8.6 — Fallas de conexión
Si la API no responde, rechaza la consulta o la conexión se corta antes de `result`, la interfaz SHALL
informarlo con un mensaje que distinga "la API no está disponible" de "la consulta falló", sin quedar en
estado "en curso".

#### Scenario: API caída
- **GIVEN** la API no disponible
- **WHEN** la persona envía una consulta
- **THEN** la interfaz indica que no puede conectarse con la API
- **AND** permite reintentar

#### Scenario: consulta rechazada
- **GIVEN** una respuesta 422 de la API
- **WHEN** la interfaz la recibe
- **THEN** muestra que la consulta no es válida

#### Scenario: corte antes del resultado
- **GIVEN** un flujo que termina sin `result` ni `error`
- **WHEN** la conexión se cierra
- **THEN** la interfaz informa que la consulta no se completó

### Requirement: R-8.7 — Idioma de la consulta
La interfaz SHALL aceptar consultas en castellano o en inglés (R-1.3) y SHALL presentar la respuesta del
agente sin traducirla ni modificarla.

#### Scenario: consulta en inglés
- **GIVEN** una consulta escrita en inglés
- **WHEN** la persona la envía
- **THEN** la interfaz la envía sin modificarla
- **AND** muestra la respuesta tal como llega

### Requirement: R-8.8 — Arranque conjunto con Docker
El sistema SHALL levantar la base, la API y la interfaz web con un único `docker compose up`, y la
interfaz SHALL quedar accesible en el navegador en un puerto local. La API y la interfaz SHALL NO arrancar
antes de que sus dependencias estén sanas.

#### Scenario: arranque completo
- **GIVEN** un `.env` con las credenciales definidas
- **WHEN** se ejecuta `docker compose up -d --wait`
- **THEN** los servicios de base, API y web quedan sanos
- **AND** la interfaz responde en el navegador

#### Scenario: la API depende de la base
- **GIVEN** la base todavía no está sana
- **WHEN** arranca el compose
- **THEN** la API no inicia hasta que la base lo esté

#### Scenario: la web llega a la API
- **GIVEN** el sistema levantado con Docker
- **WHEN** la interfaz envía una consulta
- **THEN** la API la recibe sin error de CORS ni de red

### Requirement: R-8.9 — Sin secretos en la interfaz
La interfaz y su imagen SHALL NO contener `GEMINI_API_KEY`, credenciales de la base ni el `.env`. Solo la
API y la base los reciben, por variables de entorno en tiempo de ejecución (Art. 9).

#### Scenario: imagen de la web
- **WHEN** se inspecciona la imagen de la interfaz y su contenido estático
- **THEN** no aparece ningún valor de `.env` ni de las variables secretas
