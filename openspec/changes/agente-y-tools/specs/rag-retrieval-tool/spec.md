# Spec Delta

## Purpose

Define el comportamiento de la herramienta de recuperación: cómo se indexan los documentos y cómo se
obtienen los fragmentos relevantes para una consulta, con su referencia de origen.

## ADDED Requirements

### Requirement: R-4.1 — Ingesta de documentos
El sistema SHALL extraer el texto de los documentos PDF, dividirlo en fragmentos, generar sus
embeddings y almacenarlos.

#### Scenario: ingesta completa
- **GIVEN** entre 4 y 6 PDFs en el repositorio documental
- **WHEN** se ejecuta la ingesta
- **THEN** cada documento queda representado por al menos un fragmento almacenado
- **AND** cada fragmento conserva su vector

### Requirement: R-4.2 — Identificación de cada fragmento
Cada fragmento SHALL conservar identificador, documento de origen, ubicación (página o sección), texto y vector.

#### Scenario: fragmento identificable
- **WHEN** se consulta un fragmento almacenado
- **THEN** es posible determinar a qué documento y a qué página o sección pertenece

### Requirement: R-4.3 — Chunking por cláusula con tope de 800 tokens
El sistema SHALL dividir los documentos por cláusula o párrafo, con un tope de 800 tokens y un
solapamiento de 150 tokens, sin cortar una cláusula entre fragmentos.

#### Scenario: reproducibilidad del chunking
- **GIVEN** los parámetros de chunking fijados por el propio requisito (tope 800, solapamiento 150, D10)
- **WHEN** se reejecuta la ingesta sobre el mismo documento
- **THEN** la cantidad de fragmentos coincide con lo esperado por esa configuración

#### Scenario: cláusula más larga que el tope
- **GIVEN** una cláusula del reglamento de más de 800 tokens
- **WHEN** se divide el documento
- **THEN** la cláusula queda completa en un único fragmento
- **AND** no se corta en el límite del tope

### Requirement: R-4.4 — Recuperación por similitud con umbral
La herramienta SHALL devolver los top-k fragmentos más similares por similitud de coseno, aplicando un
umbral mínimo configurable.

#### Scenario: pregunta normativa
- **GIVEN** el reglamento de biblioteca indexado con la cláusula de plazo de devolución
- **WHEN** el usuario pregunta "¿Cuántos días tengo para devolver un libro antes de que me multen?"
- **THEN** la herramienta devuelve al menos un fragmento que contiene la cláusula de plazo
- **AND** el fragmento proviene del reglamento

### Requirement: R-4.5 — Ingesta idempotente
La ingesta SHALL ser idempotente: reejecutarla sobre el mismo documento no duplica fragmentos.

#### Scenario: reingesta
- **GIVEN** fragmentos ya almacenados para `reglamento_biblioteca.pdf`
- **WHEN** se vuelve a ejecutar la ingesta sobre el mismo archivo
- **THEN** no se crean fragmentos duplicados

### Requirement: R-4.6 — Reporte de ausencia de resultados relevantes
La herramienta SHALL reportar "no se encontró información relevante" cuando la similitud máxima esté
por debajo del umbral.

#### Scenario: pregunta sin cobertura documental
- **GIVEN** un repositorio documental sin información sobre el tema consultado
- **WHEN** la similitud máxima de los fragmentos está por debajo del umbral
- **THEN** la herramienta reporta "no se encontró información relevante"
- **AND** el agente no fabrica una respuesta

### Requirement: R-4.7 — Referencia de origen para citación
Cada fragmento devuelto SHALL incluir el documento de origen, para permitir la cita en la respuesta.

#### Scenario: cita verificable
- **WHEN** la respuesta se apoya en un fragmento
- **THEN** la evidencia muestra el nombre del documento y su ubicación
- **AND** el texto citado coincide con ese fragmento

### Requirement: R-4.8 — Top-k y umbral calibrados
El top-k (5) y el umbral de similitud de coseno (0.35) SHALL estar en configuración y haberse calibrado
contra los documentos reales antes de fijarse como valor de aceptación.

#### Scenario: calibración documentada
- **WHEN** se fija el umbral de similitud
- **THEN** el valor y la evidencia de la calibración quedan registrados en el CHANGELOG
