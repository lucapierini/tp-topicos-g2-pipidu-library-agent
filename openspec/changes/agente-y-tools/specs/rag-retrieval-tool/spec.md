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

### Requirement: R-4.3 — Chunking por sección, sin tope de tokens ni solapamiento
El sistema SHALL dividir cada documento en un fragmento por sección (artículo o paso numerado), sin
cortar una sección entre fragmentos, sin tope de tokens y sin solapamiento (D10).

#### Scenario: reproducibilidad del chunking
- **GIVEN** un documento partido por sección (D10)
- **WHEN** se reejecuta la ingesta sobre el mismo documento
- **THEN** la cantidad de fragmentos es la misma que en la corrida anterior
- **AND** cada fragmento es una sección completa de ese documento

#### Scenario: sección extensa
- **GIVEN** una sección extensa del reglamento
- **WHEN** se divide el documento
- **THEN** la sección queda completa en un único fragmento
- **AND** no se corta en ningún límite de tokens

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

#### Scenario: clave de idempotencia
- **GIVEN** un documento cuyo archivo no cambió desde la última ingesta
- **WHEN** se vuelve a ejecutar la ingesta
- **THEN** el documento se saltea y su cantidad de fragmentos no cambia
- **AND** cada fragmento queda identificado de forma única por su documento y su posición (D11)

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

### Requirement: R-4.8 — Top-k y umbral en configuración, calibrados
El top-k (5) y el umbral de similitud de coseno SHALL estar en configuración y haberse calibrado
contra los documentos reales antes de fijarse como valor de aceptación. El umbral vigente es 0,64, calibrado
contra los documentos reales, y es el valor por defecto de configuración (D12).

#### Scenario: calibración documentada
- **WHEN** se fija el umbral de similitud
- **THEN** el valor y la evidencia de la calibración quedan registrados en el CHANGELOG
- **AND** el valor se lee de configuración y no del código
