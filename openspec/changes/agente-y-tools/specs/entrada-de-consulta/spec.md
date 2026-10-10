# Spec Delta

## Purpose

Define cómo el sistema recibe consultas en lenguaje natural desde la interfaz, qué acepta y qué
rechaza antes de invocar al agente.

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
- **GIVEN** la interfaz abierta
- **WHEN** el usuario envía un texto vacío
- **THEN** el sistema no invoca ninguna herramienta
- **AND** muestra un mensaje de error

#### Scenario: consulta de solo espacios
- **GIVEN** la interfaz abierta
- **WHEN** el usuario envía una cadena de espacios
- **THEN** el sistema no invoca ninguna herramienta
- **AND** muestra un mensaje de error
