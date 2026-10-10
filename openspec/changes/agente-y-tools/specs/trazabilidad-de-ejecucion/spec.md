# Spec Delta

## Purpose

Define el registro de cada consulta procesada, necesario para validar el comportamiento del agente y
producir las evidencias que el informe técnico exige.

## ADDED Requirements

### Requirement: R-6.1 — Contenido del registro
El registro SHALL incluir timestamp, pregunta, clasificación, herramientas invocadas, sentencia
generada, fragmentos recuperados, respuesta y latencia total.

#### Scenario: registro completo
- **WHEN** el agente procesa una consulta
- **THEN** el registro contiene los ocho campos enumerados

### Requirement: R-6.2 — Persistencia del registro
El registro SHALL persistir en la tabla `agent_runs`.

#### Scenario: consulta resuelta
- **WHEN** una consulta finaliza con éxito
- **THEN** existe una fila en `agent_runs` con los datos de esa consulta

### Requirement: R-6.3 — Registro de consultas rechazadas
El sistema SHALL registrar también las consultas que fallan o son rechazadas.

#### Scenario: rechazo por validación de SQL
- **GIVEN** una consulta que dispara un rechazo por validación estática
- **WHEN** el agente finaliza la ejecución
- **THEN** el registro queda persistido con el motivo del rechazo
- **AND** la latencia total queda registrada

### Requirement: R-6.4 — Registro de intentos de generación
El registro SHALL consignar la cantidad de intentos de generación de sentencia y el resultado de cada uno.

#### Scenario: consulta con regeneración
- **GIVEN** una consulta que requirió dos intentos de generación
- **WHEN** se consulta el registro
- **THEN** se observan los dos intentos con su resultado individual
