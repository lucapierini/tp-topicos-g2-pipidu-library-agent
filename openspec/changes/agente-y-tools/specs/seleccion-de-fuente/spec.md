# Spec Delta

## Purpose

Define la decisión autónoma del agente sobre qué fuente de conocimiento consultar para cada
consulta, y cómo esa decisión queda visible en la respuesta.

## ADDED Requirements

### Requirement: R-2.1 — Clasificación única de la consulta
El agente SHALL clasificar cada consulta en exactamente una categoría: `sql`, `rag`, `hybrid` o `none`.

#### Scenario: clasificación registrada
- **WHEN** el agente procesa una consulta
- **THEN** la clasificación queda registrada en el registro de ejecución
- **AND** coincide con las herramientas efectivamente invocadas

### Requirement: R-2.2 — Uso de SQL para datos estructurados
El agente SHALL clasificar la consulta como `sql` cuando la respuesta depende de datos estructurados de la base.

#### Scenario: consulta resolvable solo con datos estructurados
- **GIVEN** el socio "Juan Pérez" con préstamos activos
- **WHEN** el usuario pregunta "¿Qué libros tiene prestados Juan Pérez?"
- **THEN** el agente clasifica la consulta como `sql`
- **AND** invoca la herramienta de SQL
- **AND** no invoca la herramienta de RAG

### Requirement: R-2.3 — Uso de RAG para contenido documental
El agente SHALL clasificar la consulta como `rag` cuando la respuesta depende de contenido documental no estructurado.

#### Scenario: consulta normativa
- **GIVEN** el reglamento de biblioteca indexado
- **WHEN** el usuario pregunta "¿Cuántos días tengo para devolver un libro antes de que me multen?"
- **THEN** el agente clasifica la consulta como `rag`
- **AND** invoca la herramienta de RAG
- **AND** no invoca la herramienta de SQL

### Requirement: R-2.4 — Uso combinado cuando la consulta lo requiere
El agente SHALL clasificar la consulta como `hybrid` cuando la respuesta requiere ambas fuentes.

#### Scenario: consulta mixta de sanción
- **GIVEN** un préstamo activo de 20 días para el socio "Juan Pérez"
- **WHEN** el usuario pregunta "Juan Pérez tiene un libro prestado hace 20 días, ¿le corresponde multa según el reglamento?"
- **THEN** el agente clasifica la consulta como `hybrid`
- **AND** invoca la herramienta de SQL para la fecha del préstamo
- **AND** invoca la herramienta de RAG para la regla de sanción
- **AND** la respuesta combina ambos resultados

### Requirement: R-2.5 — Declaración de falta de cobertura
El agente SHALL clasificar la consulta como `none` cuando ninguna fuente contiene información suficiente.

#### Scenario: consulta sin cobertura
- **GIVEN** una base de datos y un repositorio documental sin información sobre el tema
- **WHEN** el usuario pregunta "¿Cuál es el precio del libro X?"
- **THEN** el agente declara que no dispone de información suficiente
- **AND** no inventa una respuesta
- **AND** declara `fuente: ninguna`

### Requirement: R-2.6 — Declaración de fuente en la respuesta
El agente SHALL declarar en la respuesta la fuente o fuentes utilizadas.

#### Scenario: fuente visible
- **WHEN** el agente entrega una respuesta
- **THEN** la respuesta indica la fuente usada (`SQL`, `RAG`, `SQL + RAG` o `ninguna`)

### Requirement: R-2.7 — Clasificación en salida estructurada obligatoria
El agente SHALL emitir la clasificación mediante una salida estructurada obligatoria antes de invocar
cualquier herramienta.

#### Scenario: clasificación previa a la invocación
- **WHEN** el agente procesa una consulta
- **THEN** emite la clasificación en formato estructurado
- **AND** la clasificación se resuelve antes de la primera invocación a herramienta

#### Scenario: clasificación inconsistente con la herramienta invocada
- **GIVEN** una clasificación `sql`
- **WHEN** el agente invoca la herramienta de RAG
- **THEN** el sistema registra la inconsistencia
- **AND** la fuente declarada en la respuesta es la efectivamente invocada
