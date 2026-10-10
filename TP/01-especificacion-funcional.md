# Especificación Funcional — Pipidu Library Agent

> Documento incremental. Se irá completando/ajustando a medida que avance el diseño.
>
> **Nivel en el ciclo SDD:** Spec (WHAT). Las capacidades detalladas del agente y sus tools están en
> `03-especificaciones-por-capacidad.md`; las tareas en `04-tareas.md`; la validación en
> `05-validacion.md`; los principios en `00-constitucion.md`.

## 1. Datos generales

- **Proyecto:** Pipidu Library Agent
- **Materia:** Tópicos Avanzados de IA — Trabajo Práctico Integrador (AI Engineering)
- **Modalidad:** Grupal (hasta 3 integrantes)
- **Integrantes:** _(completar)_
- **Fecha de entrega:** 16/10/2026 23:59 (GMT-03)
- **Coloquio:** 23/10/2026 o 30/10/2026
- **Objetivo de calificación:** Promoción directa
- **Repositorio:** GitHub — `pipidu-library-agent`

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
| Usuario final | Persona que interactúa con el agente vía interfaz web (Streamlit) haciendo preguntas en lenguaje natural |
| Agente IA | Componente que interpreta la consulta, decide la estrategia (SQL / RAG / mixta) y genera la respuesta |
| Administrador/Desarrollador | Responsable de poblar la base, cargar los PDFs e indexar embeddings |

## 5. Alcance funcional

### 5.1 Base de datos relacional
- Modelo de datos con **mínimo 6 tablas** (cumple el mínimo de 5 exigido):
  1. Socios (alumnos/docentes)
  2. Libros
  3. Autores
  4. Préstamos
  5. Categorías/Géneros
  6. Editoriales
- Cada tabla poblada con **15-20 registros sintéticos** como mínimo (cumple el mínimo de 15 exigido).
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
- Manual de uso del sistema
- Políticas generales de la universidad

Ejemplos de preguntas RAG:
- "¿Cuántos días tengo para devolver un libro antes de que me multen?"
- "¿De qué trata el libro 'X'?"
- "¿Cómo renuevo un préstamo desde el sistema?"

### 5.4 Consultas mixtas (SQL + RAG)
El agente debe poder combinar ambas fuentes cuando la consulta lo requiera, por ejemplo:
- "Juan Pérez tiene un libro prestado hace 20 días, ¿le corresponde multa según el reglamento?" (requiere SQL para saber la fecha del préstamo + RAG para la regla de sanción).

### 5.5 Exclusiones de alcance (no implementar sin cambiar esta spec)

- Memoria conversacional multi-turno (v1 es single-turn); el historial de la UI es solo visual (D17).
- Observabilidad con LangSmith o evaluación automática de respuestas.
- Fine-tuning del modelo.
- Escritura sobre la base de datos.
- Autenticación, usuarios y roles de aplicación.
- Streaming de respuestas parciales y reintentos ante fallo de API. La **regeneración de SQL** sí está
  permitida, limitada a 2 intentos (D8); al segundo rechazo se reporta el error al usuario.
- Formatos documentales distintos de PDF.

### 5.6 Interfaz de usuario
- Interfaz gráfica desarrollada en **Streamlit**, donde el usuario escribe su consulta en un campo de texto y recibe la respuesta del agente, con indicación de la(s) fuente(s) utilizada(s) (SQL / RAG / ambas).

## 6. Requisitos no funcionales

- **Reproducibilidad:** cualquier evaluador debe poder clonar el repo, seguir el README y levantar el sistema completo (BD + agente + UI).
- **Documentación:** código comentado donde sea necesario, README claro con instrucciones de instalación y ejecución.
- **Despliegue en la nube:** el agente y la base de datos deben poder ejecutarse en GCP.
- **Trazabilidad SDD:** se documentará el proceso de desarrollo siguiendo Spec Driven Development (specs funcionales y técnicas, versionadas, previas a la implementación).

## 7. Criterios de aceptación (según enunciado)

- [ ] Modelo relacional con ≥5 tablas y ≥15 registros por tabla
- [ ] El agente interpreta lenguaje natural y responde usando la base de datos
- [ ] El agente responde usando contenido de ≥2 PDFs vía RAG
- [ ] Código documentado y reproducible
- [ ] Informe técnico (máx. 10 páginas)
- [ ] Coloquio de exposición

## 8. Criterios de promoción directa (2+ de 5, elegidos 4)

- [x] Despliegue en la nube (GCP)
- [x] Interfaz gráfica (Streamlit)
- [x] Framework agéntico (Smolagents)
- [x] SDD (artefactos de esta carpeta `TP/`)
- [ ] Observabilidad (LangSmith) — no incluido

## 9. Entregables

- Repositorio GitHub con código fuente completo
- Scripts de generación de datos sintéticos + dump de la base de datos
- Carpeta con los PDFs utilizados para RAG
- README de instalación y ejecución
- Informe técnico (máx. 10 páginas)
- Artefactos SDD (specs funcional y técnica, este mismo documento y su par técnico)

## 10. Preguntas abiertas / pendientes de definir

Las preguntas de diseño se cerraron el 2026-10-10 (D1–D20 en `CHANGELOG.md`). Quedan estas, que no son
de diseño:

- Nombres de los integrantes del grupo
- Listado final y definitivo de las 4-6 preguntas de ejemplo para el informe
- Definición final del modelo de datos detallado (ver especificación técnica)
