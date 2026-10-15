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
- **AND** el resultado declara `sources` vacío

### Requirement: R-2.6 — Declaración de fuente en el resultado
El agente SHALL declarar en el resultado la fuente o fuentes utilizadas, en un campo estructurado y no
en el texto de la respuesta (R-5.2).

#### Scenario: fuente visible
- **WHEN** el agente entrega una respuesta
- **THEN** el resultado indica la fuente usada en `sources` (`sql`, `rag` o ambas; vacío si ninguna)

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

### Requirement: R-2.8 — Proveedor del modelo configurable
El sistema SHALL permitir cambiar el proveedor del modelo (clasificación y loop de herramientas) por
configuración, sin cambios de código: un servidor local compatible con la API de OpenAI durante el
desarrollo y Gemini mediante API key para la aceptación y para ejecutar el sistema (D81). El flujo
(clasificación previa, herramientas expuestas por fuente, límites de intentos y pasos, composición de la respuesta) SHALL ser el
mismo con cualquier proveedor.

#### Scenario: validación del flujo contra un modelo local
- **GIVEN** `LLM_MODEL` y `LLM_API_BASE` apuntando a un servidor local
- **WHEN** se ejecuta el golden set
- **THEN** la clasificación se emite antes de la primera herramienta y solo se exponen las herramientas de la fuente
- **AND** la ejecución no consume cuota de ninguna API externa

#### Scenario: los resultados locales no reemplazan la aceptación
- **GIVEN** una corrida del golden set contra un modelo local
- **WHEN** se evalúa el criterio R-2.1 (≥ 11/13)
- **THEN** la corrida se registra como validación del flujo y no como aceptación
- **AND** la aceptación se mide con el modelo definitivo (Gemini) y su evidencia consigna el modelo usado

#### Scenario: migración al modelo definitivo
- **GIVEN** el flujo validado contra el modelo local
- **WHEN** se cambia la configuración a Gemini con `GEMINI_API_KEY`
- **THEN** no se modifica código ni prompts
- **AND** se repite la medición completa del golden set con el modelo definitivo

#### Scenario: límite de cuota del proveedor
- **GIVEN** un proveedor que responde 429 con un tiempo de espera
- **WHEN** el sistema recibe la respuesta
- **THEN** reintenta respetando la espera indicada, hasta el máximo configurado
- **AND** si se agotan los reintentos reporta el error al usuario y no lo presenta como una clasificación
