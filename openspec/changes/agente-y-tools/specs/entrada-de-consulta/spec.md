# Spec Delta

## Purpose

Define cómo el sistema recibe consultas en lenguaje natural desde el cliente (el frontend, por la API
HTTP: `consulta-por-api`), qué acepta y qué rechaza antes de invocar al agente.

## ADDED Requirements

### Requirement: R-1.1 — Aceptación de consultas en lenguaje natural
El sistema SHALL aceptar una consulta en lenguaje natural en castellano o inglés sin restringir el
idioma de la respuesta.

#### Scenario: consulta en castellano
- **WHEN** el usuario envía una pregunta en castellano
- **THEN** el sistema la procesa
- **AND** la respuesta final está en castellano

#### Scenario: consulta en inglés
- **WHEN** el usuario envía una pregunta en inglés
- **THEN** el sistema la procesa
- **AND** la respuesta final está en inglés

### Requirement: R-1.2 — Rechazo de consultas vacías
El sistema SHALL rechazar consultas vacías o compuestas únicamente por espacios sin invocar al agente.

#### Scenario: consulta vacía
- **GIVEN** un cliente conectado a la API
- **WHEN** envía un texto vacío
- **THEN** el sistema no invoca ninguna herramienta
- **AND** responde con un error de validación (R-7.4)

#### Scenario: consulta de solo espacios
- **GIVEN** un cliente conectado a la API
- **WHEN** envía una cadena de espacios
- **THEN** el sistema no invoca ninguna herramienta
- **AND** responde con un error de validación (R-7.4)

### Requirement: R-1.3 — Consultas simultáneas atendidas en serie
El sistema SHALL atender de a una las consultas que llegan simultáneamente, de modo que no
compartan al mismo tiempo la conexión a la base ni el estado de una consulta en curso.

#### Scenario: dos consultas al mismo tiempo
- **GIVEN** dos sesiones que envían una consulta en el mismo instante
- **WHEN** el sistema las recibe
- **THEN** la segunda comienza a procesarse cuando termina la primera
- **AND** cada respuesta corresponde a su propia consulta
