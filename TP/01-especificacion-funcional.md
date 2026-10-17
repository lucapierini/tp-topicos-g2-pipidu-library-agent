# Especificación Funcional — Pipidu Library Agent

> **Nivel en el ciclo SDD:** Spec (WHAT). Las capacidades detalladas del agente y sus tools están en
> `openspec/changes/agente-y-tools/specs/<capacidad>/spec.md`; las tareas en
> `openspec/changes/agente-y-tools/tasks.md`; la validación en `05-validacion.md`; los principios en
> `00-constitucion.md`.

## 1. Datos generales

- **Proyecto:** Pipidu Library Agent
- **Materia:** Tópicos Avanzados de IA (UCSE, Ingeniería en Informática)
- **Integrantes:** Duelli, Agustín · Pierini, Luca · Pistarino, Bruno
- **Repositorio:** GitHub — `tp-topicos-g2-pipidu-library-agent`

## 2. Dominio

**Biblioteca universitaria**: gestión de préstamos de libros, socios (alumnos y docentes), catálogo bibliográfico,
autores, editoriales y categorías temáticas. La base de datos se complementa con documentación institucional
(reglamento, políticas y reseñas de libros) que el agente consulta con RAG.

## 3. Objetivo

Un agente de IA que:

1. Recibe consultas en lenguaje natural, en castellano o en inglés, sobre el dominio de la biblioteca.
2. Decide en cada consulta si se resuelve contra la base de datos relacional (SQL), contra el repositorio
   documental (RAG) o combinando las dos fuentes.
3. Devuelve una respuesta clara, en el idioma de la consulta, que declara su fuente y su evidencia.
4. Cuando la consulta es solo un saludo, responde con una bienvenida y dos consultas de ejemplo.

## 4. Actores

| Actor | Descripción |
|---|---|
| Usuario final | Persona que hace preguntas en lenguaje natural desde la interfaz web (`web/`, D93), que consulta al agente por la API HTTP (D80) |
| Agente de IA | Componente que interpreta la consulta, decide la estrategia (SQL, RAG o mixta) y compone la respuesta |
| Administrador o desarrollador | Responsable de poblar la base, cargar los PDF e indexar los embeddings |

## 5. Alcance funcional

### 5.1 Base de datos relacional

El modelo tiene **7 tablas** (`db/schema.sql`, D64):

1. Socios (alumnos y docentes)
2. Libros
3. Autores
4. Préstamos
5. Categorías
6. Editoriales
7. `libros_autores` (relación N:M entre libros y autores; no existe `libros.autor_id`, D64)

El repositorio documental (`documentos` y `documentos_chunks`) es el índice del RAG y no forma parte del modelo
relacional del dominio: se describe en la especificación técnica (§3.2.1).

Cada tabla tiene **al menos 15 registros**: el seed completo carga entre 18 y 95. Los datos son coherentes y
permiten consultas con joins, agregaciones, filtros y rankings.

### 5.2 Consultas en lenguaje natural resueltas con SQL

El agente responde preguntas como las siguientes (ejemplos no exhaustivos):

- «¿Qué libros tiene prestados el socio Juan Pérez?»
- «¿Cuáles son los 5 libros más prestados este cuatrimestre?»
- «¿Qué socios tienen préstamos vencidos?»
- «¿Cuántos libros de la categoría "Ciencias de la Computación" hay disponibles?»
- «¿Qué autor tiene más libros publicados por la editorial X?»

### 5.3 Consultas resueltas con RAG

El agente responde preguntas que requieren contenido no estructurado a partir de **6 documentos PDF**:

- Reglamento de la biblioteca (normas de préstamo, sanciones, horarios).
- Políticas generales de la universidad.
- Reseñas y sinopsis de libros y sagas del catálogo.

Ejemplos:

- «¿Cuántos días tengo para devolver un libro antes de que me multen?»
- «¿De qué trata el libro "X"?»
- «¿Cómo renuevo un préstamo desde el sistema?»

### 5.4 Consultas mixtas (SQL y RAG)

El agente combina las dos fuentes cuando la consulta lo requiere. Por ejemplo, «Juan Pérez tiene un libro prestado
hace 20 días, ¿le corresponde multa según el reglamento?» necesita SQL para saber la fecha del préstamo y RAG para
conocer la regla de sanción.

### 5.5 Exclusiones de alcance (no implementar sin cambiar esta spec)

- Memoria conversacional multi-turno: cada consulta es independiente. El historial lo conserva el frontend
  (la interfaz acumula las consultas de la sesión en pantalla, R-8.10) y no alimenta al agente (D17, R-7.0).
- Observabilidad con LangSmith o evaluación automática de respuestas.
- Fine-tuning del modelo.
- Escritura sobre la base de datos.
- Autenticación, usuarios y roles de aplicación.
- Política de privacidad o restricción de columnas por PII: todos los usuarios acceden a toda la información del
  dominio (Art. 11). La whitelist es control de alcance y de inyección.
- Streaming de **tokens** del modelo y respuestas parciales: la respuesta se compone al final con las fuentes
  efectivamente invocadas (D58, D75). Sí está permitido el streaming de **progreso** de la consulta por la API HTTP
  (D75) y el reintento ante límite de cuota (D57).
- La **regeneración de SQL** está permitida, limitada a 2 intentos (D8); al segundo rechazo se reporta el error al
  usuario.
- Formatos documentales distintos de PDF.

### 5.6 Acceso al agente e interfaz de usuario

- El agente se consulta **únicamente por la API HTTP** (`POST /ask`, con respuesta en streaming de progreso;
  capacidad `consulta-por-api`, D75, D80). El servidor del agente no incluye interfaz gráfica: la interfaz es un
  cliente de la API (D93).
- La interfaz gráfica es la **SPA de `web/`** (capacidad `interfaz-web`, D93). El usuario escribe su consulta en un
  campo de texto y la SPA muestra el progreso, la respuesta con la fuente utilizada (SQL, RAG o ambas) y la
  evidencia que entrega el evento `result`.

## 6. Requisitos no funcionales

- **Reproducibilidad:** cualquier persona puede clonar el repositorio, seguir el README y levantar el sistema
  completo (base de datos, ingesta del RAG, API e interfaz web) con `docker compose up -d --build --wait`
  (D91, D92, D93).
- **Documentación:** código comentado donde hace falta y un README con las instrucciones de instalación y ejecución.
- **Ejecución local:** el sistema corre en Docker Compose (Postgres con pgvector, API del agente e interfaz web);
  la API también corre con `uvicorn api.app:app`. No usa servicios de nube (D81).
- **Trazabilidad SDD:** el desarrollo sigue Spec Driven Development: specs funcionales y técnicas, versionadas y
  previas a la implementación.

## 7. Criterios de aceptación del sistema

- [x] El modelo relacional tiene 7 tablas con al menos 15 registros cada una (`db/schema.sql`, `db/seed.sql`).
- [x] El agente interpreta consultas en lenguaje natural, en castellano y en inglés, y responde con la base de datos
  (`tests/test_golden_set.py`, `TP/evidencia/golden_gemini-3.1-flash-lite_2026-10-11_db-mock.json`).
- [x] El agente responde con contenido de los 6 PDF mediante RAG (`rag/documents/pdf/`).
- [x] El código está documentado y es reproducible (`README.md`, `docker-compose.yml`).

## 8. Componentes del sistema

- **Interfaz gráfica:** SPA en `web/` que consume la API (D80, D93).
- **Framework agéntico:** Smolagents (`ToolCallingAgent`, D2).
- **Spec Driven Development:** artefactos de `TP/` y de `openspec/`.
- **Trazabilidad de ejecución:** tabla `agent_runs` con cada consulta, sus herramientas, el SQL y los fragmentos
  usados (Art. 5).

## 9. Contenido del repositorio

- Código fuente completo del agente, la API y la interfaz web.
- Datos de prueba de la base (`db/seed.sql`, `db/dev_seed.sql`).
- Documentos fuente del RAG, en Markdown y en PDF (`rag/documents/`).
- README con la instalación y la ejecución.
- Artefactos SDD: especificaciones funcional y técnica, constitución, validación, registro de decisiones y evidencia.
- Informe técnico (`informe/`).
