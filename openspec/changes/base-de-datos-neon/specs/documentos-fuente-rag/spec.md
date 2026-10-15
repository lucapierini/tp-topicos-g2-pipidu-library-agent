# Spec Delta

## Purpose

Define los documentos que alimentan el RAG, la consistencia entre ellos y cómo se versionan y
almacenan sus originales, antes de que exista la ingesta.

## ADDED Requirements

### Requirement: R-9.1 — Entre 4 y 6 documentos fuente
El repositorio SHALL contener entre 4 y 6 documentos fuente en Markdown en `rag/documents/`.

#### Scenario: inventario
- **WHEN** se listan los `.md` de `rag/documents/`
- **THEN** hay 6: `reglamento_biblioteca`, `politicas_universidad`, `resenas_cien_anios_de_soledad`, `resenas_clean_code`, `resenas_tolkien`, `resenas_empyrean`

### Requirement: R-9.2 — El reglamento es la fuente de las reglas de negocio
`reglamento_biblioteca.md` SHALL declarar plazo de préstamo, máximo de libros simultáneos, renovaciones y multa por atraso, y SHALL ser la única fuente de esas reglas.

#### Scenario: reglas por tipo de socio
- **WHEN** se lee el reglamento
- **THEN** alumno: 14 días, 3 libros, 1 renovación de +7 días
- **AND** docente: 30 días, 5 libros, 1 renovación de +14 días
- **AND** multa de $200 por día de atraso y por libro, para ambos

### Requirement: R-9.3 — Consistencia entre documentos
Ninguna regla repetida en otro documento SHALL contradecir al reglamento.

#### Scenario: sanciones en las políticas
- **GIVEN** las políticas, que mencionan préstamos, renovaciones, multas o sanciones
- **WHEN** se comparan con el reglamento
- **THEN** ningún valor ni condición lo contradice

### Requirement: R-9.4 — Estructura citable
Los documentos SHALL organizarse en artículos o secciones numeradas, de modo que un fragmento pueda citarse como "Art. N" o "§ N".

#### Scenario: cita por artículo
- **WHEN** se busca el plazo de préstamo
- **THEN** figura bajo un título numerado (`Artículo 2`)

### Requirement: R-9.5 — PDFs versionados
Cada documento fuente SHALL tener su PDF en `rag/documents/pdf/`, generado con `rag/build_pdfs.py`, porque el enunciado exige PDFs.

#### Scenario: extracción de texto
- **GIVEN** un PDF generado
- **WHEN** se extrae su texto con `pypdf`
- **THEN** contiene el contenido del Markdown de origen

### Requirement: R-9.6 — Originales en bucket privado
Los PDFs SHALL almacenarse en el bucket privado `rag` de Neon bajo el prefijo `documents/`, y la subida MUST ser idempotente.

#### Scenario: subida repetida
- **WHEN** se ejecuta `rag/upload_to_bucket.py` dos veces
- **THEN** el bucket queda con un objeto por PDF, sin duplicados

#### Scenario: sin secretos versionados
- **WHEN** se revisa el árbol versionado
- **THEN** las credenciales S3 solo existen en `.env.local`, que está en `.gitignore`

### Requirement: R-9.7 — Los casos del golden set tienen respaldo documental
Los documentos SHALL cubrir plazo de devolución, horarios y la sinopsis de las obras reseñadas (Cien años de soledad, Clean Code, la obra de Tolkien y la saga Empyrean).

#### Scenario: cobertura
- **WHEN** se contrastan los casos RAG e híbridos del golden set con los documentos
- **THEN** cada uno tiene al menos un fragmento fuente
