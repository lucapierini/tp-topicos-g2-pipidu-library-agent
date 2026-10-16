# Spec Delta

## Purpose

Define el contenido y la calidad del seed que puebla la base, para que las consultas del golden set
tengan datos reales sobre los que responder.

## ADDED Requirements

### Requirement: R-8.1 — Catálogo real, socios y préstamos sintéticos
El seed SHALL cargar un catálogo de libros reales (título, autores, editorial, ISBN y año verificables) y socios y préstamos sintéticos.

#### Scenario: volumen mínimo
- **GIVEN** el seed aplicado sobre el esquema vacío
- **WHEN** se cuentan las filas de las 7 tablas de dominio
- **THEN** cada una tiene al menos 15 registros

#### Scenario: ISBN únicos
- **WHEN** se consulta `libros`
- **THEN** no hay dos libros con el mismo ISBN

### Requirement: R-8.2 — Fechas relativas a la fecha de carga
Las fechas de los préstamos SHALL calcularse relativas a `CURRENT_DATE`, de modo que siempre existan préstamos activos y vencidos.

#### Scenario: hay vencidos
- **GIVEN** el seed aplicado en cualquier fecha
- **WHEN** se consulta `v_prestamos_estado` por `estado_calculado = 'vencido'`
- **THEN** hay al menos un préstamo vencido

### Requirement: R-8.3 — Los libros reseñados existen en el catálogo (reemplazado por R-8.8)
El catálogo SHALL incluir los libros reseñados en `documentos-fuente-rag`: *Cien años de soledad*, *Clean Code* y *Artificial Intelligence: A Modern Approach*.

#### Scenario: cruce entre fuentes
- **WHEN** se busca cada título reseñado en `libros`
- **THEN** existe una fila por título

### Requirement: R-8.4 — Datos que habilitan la consulta mixta
Los socios SHALL tener `tipo_socio` (`alumno` o `docente`) y cada préstamo `fecha_prestamo` y `fecha_devolucion_prevista`, sin ningún dato de multa ni de plazo reglamentario.

#### Scenario: consulta mixta
- **GIVEN** un socio alumno con un préstamo de hace 20 días
- **WHEN** el agente consulta SQL por la fecha y el tipo de socio, y RAG por plazo y multa
- **THEN** ambas fuentes son necesarias para calcular la multa

### Requirement: R-8.5 — Consistencia de los datos
El seed SHALL respetar las restricciones del esquema: ningún `ejemplares_disponibles > ejemplares_totales`, y todo préstamo vencido cumple `fecha_devolucion_real IS NULL AND CURRENT_DATE > fecha_devolucion_prevista`.

#### Scenario: carga sin violaciones
- **WHEN** se aplica el seed
- **THEN** la transacción termina sin errores de CHECK, UNIQUE ni FK

### Requirement: R-8.6 — Aplicación única
El seed SHALL abortar sin modificar la base si ya existen libros o socios.

#### Scenario: segunda aplicación
- **GIVEN** una base ya poblada
- **WHEN** se vuelve a aplicar el seed
- **THEN** falla con un mensaje explícito
- **AND** no cambia ninguna fila

### Requirement: R-8.7 — Catálogo ampliado en un único seed
`db/seed.sql` SHALL incluir, además del catálogo base, cómics, fantasía y manga con ISBN verificables (51 libros más, 70 en total), sin archivos de seed adicionales.

#### Scenario: seed único
- **GIVEN** una base vacía con `db/schema.sql` aplicado
- **WHEN** se aplica `db/seed.sql`
- **THEN** quedan 70 libros, 57 autores, 28 editoriales, 18 categorías y 95 vínculos libro-autor

#### Scenario: volumen y unicidad
- **WHEN** se aplica `db/seed.sql`
- **THEN** los 51 libros de la ampliación se suman con ISBN-13 únicos y de dígito verificador válido, cada uno con al menos un autor

#### Scenario: libros reseñados
- **WHEN** se buscan en `libros` los títulos reseñados en `resenas_tolkien` y `resenas_empyrean`
- **THEN** existen los 8: El Silmarillion, El Hobbit, los 3 tomos de El Señor de los Anillos, Alas de sangre, Alas de hierro y Alas de ónix

### Requirement: R-8.8 — El catálogo cubre los títulos reseñados
El catálogo SHALL incluir cada título reseñado en los documentos fuente del RAG: *Cien años de soledad*, *Clean Code*, los 5 títulos de Tolkien y los 3 de la saga Empyrean. *Artificial Intelligence: A Modern Approach* sigue en el catálogo y ya no tiene reseña (D87).

#### Scenario: cruce entre fuentes
- **GIVEN** los 6 documentos de `rag/documents/`
- **WHEN** se busca cada título reseñado en `libros`
- **THEN** existe una fila por título
- **AND** no hay reseña cuyo título falte en el catálogo

