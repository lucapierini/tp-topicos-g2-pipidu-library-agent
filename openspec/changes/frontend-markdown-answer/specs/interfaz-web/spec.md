# Spec Delta

## ADDED Requirements

### Requirement: R-8.11 — Respuesta formateada como Markdown
La interfaz SHALL presentar `answer` (con `answer_kind` `answer`) interpretado como Markdown con tablas GFM,
sin mostrar los marcadores de formato como texto, sin interpretar HTML y sin alterar el contenido (R-8.7). Los
enlaces SHALL abrirse en otra pestaña. `no_coverage`, `error` (R-8.3) y la evidencia (R-8.4) SHALL conservar su presentación.

#### Scenario: lista con negritas
- **GIVEN** un `result` cuyo `answer` es `"Libros:\n\n*   **Clean Code**\n*   **Alas de sangre**"`
- **WHEN** la interfaz lo muestra
- **THEN** ve una lista de dos ítems con los títulos en negrita
- **AND** no aparece ningún `*` en pantalla

#### Scenario: tabla Markdown
- **GIVEN** un `answer` con una tabla GFM de dos columnas
- **WHEN** la interfaz lo muestra
- **THEN** la tabla se presenta con el componente `Table` de la interfaz, con su encabezado y sus filas

#### Scenario: HTML en la respuesta
- **GIVEN** un `answer` que contiene `<script>` o `<img onerror=...>`
- **WHEN** la interfaz lo muestra
- **THEN** el HTML no se interpreta ni se ejecuta

#### Scenario: texto sin formato
- **GIVEN** un `answer` en texto plano con saltos de línea y sin marcas de Markdown
- **WHEN** la interfaz lo muestra
- **THEN** el texto se ve completo y legible, sin alterarse

#### Scenario: sin cobertura y error
- **GIVEN** un `result` con `answer_kind` `no_coverage` o `error` cuyo texto contiene marcas de Markdown
- **WHEN** la interfaz lo muestra
- **THEN** lo presenta con el `Alert` de R-8.3, sin pasar por el formato de respuesta
