# Spec Delta

## Purpose

Define cómo el agente redacta la respuesta final: idioma, declaración de fuente y evidencia
exhibida, y qué no puede afirmar.

## ADDED Requirements

### Requirement: R-5.1 — Idioma de la respuesta
La respuesta SHALL estar en el idioma de la consulta entrante.

#### Scenario: consulta en inglés
- **WHEN** el usuario pregunta en inglés
- **THEN** la respuesta está en inglés

#### Scenario: consulta en castellano
- **WHEN** el usuario pregunta en castellano
- **THEN** la respuesta está en castellano

#### Scenario: fuentes en otro idioma que la consulta
- **GIVEN** una consulta en inglés cuyas fuentes (filas, documentos) están en castellano
- **WHEN** el agente compone la respuesta
- **THEN** la respuesta completa está en inglés, no solo la línea de fuente
- **AND** la evidencia consigna el idioma con el que se compuso

### Requirement: R-5.2 — Proveniencia obligatoria
La respuesta SHALL declarar la fuente o fuentes utilizadas.

#### Scenario: respuesta con fuente SQL
- **GIVEN** una consulta clasificada como `sql`
- **WHEN** el agente compone la respuesta
- **THEN** la respuesta declara `fuente: SQL`

#### Scenario: respuesta sin fuente
- **GIVEN** una consulta clasificada como `none`
- **WHEN** el agente compone la respuesta
- **THEN** la respuesta declara `fuente: ninguna`
- **AND** no contiene afirmaciones sobre datos del dominio

### Requirement: R-5.3 — Evidencia de fuente SQL
Cuando la fuente sea SQL, la respuesta SHALL exhibir la sentencia ejecutada.

#### Scenario: sentencia exhibida
- **WHEN** la respuesta se apoya en SQL
- **THEN** se muestra la sentencia ejecutada
- **AND** los valores citados coinciden con las filas devueltas

### Requirement: R-5.4 — Evidencia de fuente RAG
Cuando la fuente sea RAG, la respuesta SHALL exhibir los fragmentos utilizados con su referencia.

#### Scenario: fragmento exhibido
- **WHEN** la respuesta se apoya en RAG
- **THEN** se muestra el fragmento citado con documento y ubicación

### Requirement: R-5.5 — Separación entre hecho verificado y razonamiento
La respuesta SHALL distinguir entre hecho verificado por una fuente y razonamiento del agente.

#### Scenario: conclusión derivada
- **GIVEN** una consulta híbrida donde el hecho proviene de SQL y la regla de RAG
- **WHEN** el agente concluye una sanción
- **THEN** la respuesta separa el hecho verificado de la conclusión derivada

### Requirement: R-5.6 — Respuesta autocontenida
La respuesta SHALL ser comprensible sin necesidad de leer la evidencia.

#### Scenario: lectura sin evidencia
- **WHEN** el usuario lee solo el cuerpo de la respuesta
- **THEN** entiende la conclusión sin consultar la sección de evidencia

### Requirement: R-5.7 — Reporte de error de herramienta
Cuando una herramienta devuelve un error, la respuesta SHALL informar ese error al usuario en lugar de
responder sin datos.

#### Scenario: error de validación de SQL
- **GIVEN** una sentencia rechazada por la validación estática en los dos intentos
- **WHEN** el agente compone la respuesta
- **THEN** la respuesta informa el motivo del rechazo
- **AND** no contiene afirmaciones sobre datos del dominio
