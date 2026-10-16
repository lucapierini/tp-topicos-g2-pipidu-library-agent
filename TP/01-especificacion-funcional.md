# Especificación Funcional — Pipidu Library Agent

> **Nivel en el ciclo SDD:** Spec (WHAT). Las capacidades detalladas del agente y sus tools están en
> `openspec/changes/agente-y-tools/specs/<capacidad>/spec.md`; las tareas en
> `openspec/changes/agente-y-tools/tasks.md`; la validación en `05-validacion.md`; los principios en
> `00-constitucion.md`.

## 1. Datos generales

- **Proyecto:** Pipidu Library Agent
- **Materia:** Tópicos Avanzados de IA — Trabajo Práctico Integrador (AI Engineering)
- **Modalidad:** Grupal (hasta 3 integrantes)
- **Fecha de entrega:** 16/10/2026 23:59 (GMT-03)
- **Coloquio:** 23/10/2026 o 30/10/2026
- **Objetivo de calificación:** Promoción directa
- **Repositorio:** GitHub — `tp-topicos-g2-pipidu-library-agent`

## 2. Dominio elegido

**Biblioteca universitaria**: sistema de gestión de préstamos de libros, socios (alumnos/docentes), catálogo bibliográfico, autores, editoriales y categorías temáticas, complementado con documentación institucional (reglamentos, reseñas de libros, manuales, políticas) accesible vía RAG.

## 3. Objetivo del trabajo

Desarrollar un **SQL AI Agent** capaz de:
1. Recibir consultas en lenguaje natural (castellano o inglés) sobre el dominio de biblioteca.
2. Decidir autónomamente si la consulta debe resolverse contra la base de datos relacional (SQL), contra el repositorio documental (RAG), o combinando ambas fuentes.
3. Devolver una respuesta correcta, clara y trazable al usuario.

## 4. Actores

| Actor | Descripción |
|---|---|
| Usuario final | Persona que interactúa con el agente a través de la interfaz web del repositorio (`web/`, D93), que lo consulta por la API HTTP (D80) haciendo preguntas en lenguaje natural |
| Agente IA | Componente que interpreta la consulta, decide la estrategia (SQL / RAG / mixta) y genera la respuesta |
| Administrador/Desarrollador | Responsable de poblar la base, cargar los PDFs e indexar embeddings |

## 5. Alcance funcional

### 5.1 Base de datos relacional
- Modelo de datos con **mínimo 6 tablas** (cumple el mínimo de 5 exigido). Son 7, según `db/schema.sql` (D64):
  1. Socios (alumnos/docentes)
  2. Libros
  3. Autores
  4. Préstamos
  5. Categorías/Géneros
  6. Editoriales
  7. `libros_autores` (relación N:M libros-autores; no existe `libros.autor_id`, D64)
- El repositorio documental (`documentos` y `documentos_chunks`) es el índice RAG, no una tabla del modelo
  relacional: se describe en la especificación técnica (§3.2.1).
- Cada tabla con **al menos 15 registros** (el seed completo carga entre 18 y 95).
- Los datos deben ser coherentes y permitir consultas significativas (joins, agregaciones, filtros, rankings).

### 5.2 Consultas en lenguaje natural → SQL
El agente debe poder responder preguntas del estilo (ejemplos no exhaustivos):
- "¿Qué libros tiene prestados el socio Juan Pérez?"
- "¿Cuáles son los 5 libros más prestados este cuatrimestre?"
- "¿Qué socios tienen préstamos vencidos?"
- "¿Cuántos libros de la categoría 'Ciencias de la Computación' hay disponibles?"
- "¿Qué autor tiene más libros publicados por la editorial X?"

### 5.3 Funcionalidad RAG
El agente debe responder preguntas que requieren contenido no estructurado, usando un repositorio de **4 a 6 PDFs** (mínimo exigido: 2), compuesto por:
- Reglamento de biblioteca (normas de préstamo, sanciones, horarios)
- Reseñas/sinopsis de libros del catálogo
- Políticas generales de la universidad

Ejemplos de preguntas RAG:
- "¿Cuántos días tengo para devolver un libro antes de que me multen?"
- "¿De qué trata el libro 'X'?"
- "¿Cómo renuevo un préstamo desde el sistema?"

### 5.4 Consultas mixtas (SQL + RAG)
El agente debe poder combinar ambas fuentes cuando la consulta lo requiera, por ejemplo:
- "Juan Pérez tiene un libro prestado hace 20 días, ¿le corresponde multa según el reglamento?" (requiere SQL para saber la fecha del préstamo + RAG para la regla de sanción).

### 5.5 Exclusiones de alcance (no implementar sin cambiar esta spec)

- Memoria conversacional multi-turno (v1 es single-turn); el historial lo conserva el frontend (la interfaz acumula las consultas de la sesión en pantalla, R-8.10) y no alimenta al agente (D17, R-7.0).
- Observabilidad con LangSmith o evaluación automática de respuestas.
- Fine-tuning del modelo.
- Escritura sobre la base de datos.
- Autenticación, usuarios y roles de aplicación.
- Política de privacidad o restricción de columnas por PII: todos los usuarios acceden a toda la
  información del dominio (Art. 11). La whitelist es control de alcance y de inyección.
- Streaming de **tokens** del modelo y respuestas parciales: la respuesta se compone al final con las
  fuentes efectivamente invocadas (D58, D75). Sí está permitido el streaming de **progreso** de la consulta
  por la API HTTP (D75) y el reintento ante límite de cuota (D57).
- La **regeneración de SQL** sí está permitida, limitada a 2 intentos (D8); al segundo rechazo se reporta
  el error al usuario.
- Formatos documentales distintos de PDF.

### 5.6 Acceso al agente e interfaz de usuario
- El agente se consulta **únicamente por la API HTTP** (`POST /ask`, respuesta en streaming de progreso; capacidad `consulta-por-api`, D75, D80). El servidor del agente no incluye interfaz gráfica: la interfaz es un cliente de la API (D93).
- La interfaz gráfica es la **SPA de `web/`** (capacidad `interfaz-web`, D93), un cliente que consume la API: el usuario escribe su consulta en un campo de texto y el frontend muestra la respuesta del agente con indicación de la(s) fuente(s) utilizada(s) (SQL / RAG / ambas) y la evidencia que entrega el evento `result`.

## 6. Requisitos no funcionales

- **Reproducibilidad:** cualquier evaluador debe poder clonar el repo, seguir el README y levantar el sistema completo (BD + ingesta del RAG + API + interfaz web) con `docker compose up -d --build --wait` (D91, D92, D93).
- **Documentación:** código comentado donde sea necesario, README claro con instrucciones de instalación y ejecución.
- **Despliegue en entorno local:** el sistema se ejecuta en entorno local (Docker Compose con
  Postgres + pgvector, API del agente e interfaz web; la API también corre con `uvicorn api.app:app`), sin ningún
  servicio de nube (D81).
- **Trazabilidad SDD:** el proceso de desarrollo sigue Spec Driven Development (specs funcionales y técnicas, versionadas, previas a la implementación).

## 7. Criterios de aceptación (según enunciado)

- [x] Modelo relacional con ≥5 tablas y ≥15 registros por tabla (`db/schema.sql`, `db/seed.sql`)
- [x] El agente interpreta lenguaje natural y responde usando la base de datos (`tests/test_golden_set.py`, `TP/evidencia/golden_gemini-3.1-flash-lite_2026-10-11_db-mock.json`)
- [x] El agente responde usando contenido de ≥2 PDFs vía RAG (`rag/documents/pdf/`, 6 PDFs)
- [x] Código documentado y reproducible (`README.md`, `docker-compose.yml`)

## 8. Criterios de promoción directa cubiertos (2+ de 5)

- [x] Interfaz gráfica: SPA en `web/` que consume la API (D80, D93)
- [x] Framework agéntico (Smolagents)
- [x] SDD (artefactos de esta carpeta `TP/`)

## 9. Entregables

- Repositorio GitHub con código fuente completo
- Datos de prueba de la base (`db/seed.sql`, `db/dev_seed.sql`)
- Carpeta con los PDFs utilizados para RAG
- README de instalación y ejecución
- Artefactos SDD (specs funcional y técnica, este mismo documento y su par técnico)
