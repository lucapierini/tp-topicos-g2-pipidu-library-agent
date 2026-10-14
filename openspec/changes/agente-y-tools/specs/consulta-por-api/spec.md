# Spec Delta

## Purpose

Define cómo el frontend (un cliente externo a este sistema) consulta al agente por HTTP y cómo sigue
el progreso de una consulta que puede tardar de segundos a minutos (cuota de la API del modelo). La API
es el **único** punto de acceso al agente: este sistema no incluye interfaz gráfica propia.

## ADDED Requirements

### Requirement: R-7.0 — La API es el único punto de acceso al agente
El sistema SHALL ofrecer el acceso al agente exclusivamente por la API HTTP. El sistema SHALL NO
incluir una interfaz gráfica propia: la presentación de la respuesta, la evidencia y el historial
corresponden al frontend que consume la API.

#### Scenario: imagen desplegada
- **GIVEN** la imagen que se despliega
- **WHEN** arranca
- **THEN** sirve la API HTTP
- **AND** no sirve ninguna interfaz gráfica

#### Scenario: el historial no pertenece al agente
- **GIVEN** un frontend que conserva el historial de una conversación
- **WHEN** envía una nueva consulta
- **THEN** el agente la procesa sin recibir las consultas anteriores (v1 es de un solo turno)

### Requirement: R-7.1 — Consulta por HTTP con respuesta en streaming
El sistema SHALL exponer `POST /ask` con `{"question": "<texto>"}` y responder con un flujo de
eventos que SHALL terminar con un evento `result` que contiene la respuesta completa del agente.

#### Scenario: consulta resuelta
- **GIVEN** una consulta válida en lenguaje natural
- **WHEN** el cliente la envía a `POST /ask`
- **THEN** la respuesta es un flujo de eventos
- **AND** el primer evento es `start`
- **AND** el último evento es `result` con `answer`, `answer_kind`, `sources`, `evidence` y `run_id`

#### Scenario: filas con fechas y decimales
- **GIVEN** una consulta cuyas filas incluyen fechas y valores decimales
- **WHEN** se emite el evento `result`
- **THEN** esos valores se serializan como texto sin provocar un error

### Requirement: R-7.2 — Progreso observable y sin proveniencia anticipada
El flujo SHALL informar el progreso real del agente en el orden en que ocurre: `classified`,
`tool_call`, `tool_result`, `step` y `composing`. El flujo SHALL declarar fuentes únicamente en el
evento `result`.

#### Scenario: consulta con herramienta
- **WHEN** el agente clasifica, invoca una herramienta y compone la respuesta
- **THEN** los eventos llegan en ese orden, antes de `result`

#### Scenario: solo el resultado declara fuentes
- **WHEN** se examina el flujo completo de una consulta resuelta
- **THEN** el único evento con el campo `sources` es `result`
- **AND** el progreso anterior no constituye una respuesta con proveniencia (Art. 4)

### Requirement: R-7.3 — Latido durante la espera
Mientras el agente trabaja sin emitir eventos, el sistema SHALL enviar un evento `heartbeat` con
los segundos transcurridos a intervalos de 5 segundos. El resultado SHALL entregarse al terminar el
agente, sin esperar al siguiente intervalo.

#### Scenario: espera larga
- **GIVEN** una consulta que tarda más que el intervalo de latido sin emitir eventos
- **WHEN** vence el intervalo
- **THEN** se envía `heartbeat` con `elapsed_s`
- **AND** la conexión permanece abierta hasta `result`

#### Scenario: el resultado no se demora
- **GIVEN** una consulta cuyo último evento ya fue enviado
- **WHEN** el agente termina
- **THEN** `result` se envía de inmediato, sin esperar al intervalo de latido

### Requirement: R-7.4 — Rechazo de consulta vacía
El sistema SHALL responder 422 a una consulta vacía o de solo espacios, sin abrir el flujo y sin
invocar al agente (R-1.2).

#### Scenario: consulta vacía por HTTP
- **WHEN** el cliente envía `{"question": "   "}`
- **THEN** la respuesta es 422
- **AND** no se invoca al agente

### Requirement: R-7.5 — Cancelación por desconexión del cliente
Si el cliente cierra la conexión antes de `result`, el sistema SHALL detener al agente antes del
siguiente paso, SHALL NO emitir `result` y SHALL NO registrar la consulta (R-6.7).

#### Scenario: el cliente abandona
- **GIVEN** una consulta en curso
- **WHEN** el cliente cierra la conexión
- **THEN** el agente recibe la señal de cancelación
- **AND** una llamada al modelo ya en vuelo termina, pero no se inicia otro paso

### Requirement: R-7.6 — Error inesperado informado en el flujo
Si el agente lanza una excepción inesperada, el sistema SHALL enviar un evento `error` con el
detalle y SHALL cerrar el flujo de forma ordenada, sin enviar `result`.

#### Scenario: fallo del agente
- **GIVEN** una consulta cuyo procesamiento lanza una excepción no prevista
- **WHEN** se produce el fallo
- **THEN** el flujo contiene `start` y `error`
- **AND** no contiene `result`

### Requirement: R-7.7 — Estado del servicio
El sistema SHALL exponer `GET /health`, que responde `{"status": "ok"}` sin invocar al agente ni
a la base.

#### Scenario: comprobación de salud
- **WHEN** el cliente consulta `GET /health`
- **THEN** la respuesta es 200 con `{"status": "ok"}`
- **AND** no se invoca al agente

### Requirement: R-7.8 — Orígenes permitidos (CORS)
El sistema SHALL aceptar las llamadas del frontend únicamente desde los orígenes declarados en
`API_ALLOWED_ORIGINS`. Un origen no declarado SHALL NO recibir `Access-Control-Allow-Origin` y su
preflight SHALL ser rechazado. El sistema SHALL NO usar un wildcard `*`. El acceso no requiere
autenticación: el servicio corre en entorno local (D81).

#### Scenario: origen permitido
- **GIVEN** un origen declarado en `API_ALLOWED_ORIGINS`
- **WHEN** el navegador envía un preflight `OPTIONS` a `POST /ask`
- **THEN** la respuesta es 200
- **AND** `Access-Control-Allow-Origin` es ese origen

#### Scenario: origen no declarado
- **GIVEN** un origen que no está en `API_ALLOWED_ORIGINS`
- **WHEN** envía un preflight
- **THEN** es rechazado
- **AND** la respuesta no incluye `Access-Control-Allow-Origin`

#### Scenario: sin orígenes configurados
- **GIVEN** `API_ALLOWED_ORIGINS` vacío
- **WHEN** una llamada llega desde un origen de navegador
- **THEN** la respuesta no incluye `Access-Control-Allow-Origin`

#### Scenario: sin credenciales
- **GIVEN** un origen permitido
- **WHEN** llama a `POST /ask` sin credenciales
- **THEN** la consulta se procesa
- **AND** la respuesta no refleja credenciales de la aplicación
