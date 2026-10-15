# Design

## Context

La similitud de coseno entre la consulta y un fragmento mide cercanía temática, no que el fragmento conteste. Por
eso «¿hay wifi en la sala de lectura?» se parece al reglamento (habla de la biblioteca y sus salas) aunque ningún
documento mencione el wifi. El umbral filtra el top-k: sin él, toda consulta recibe sus 5 fragmentos «menos
malos»; con uno demasiado alto se rechazan preguntas válidas. Las dos clases de consultas se solapan, así que
elegir el valor es una decisión de compromiso que necesita datos.

## Goals / Non-Goals

**Goals:**
- Medir el umbral con suficientes consultas como para que ningún caso aislado lo defina.
- Que las etiquetas del set no se pudran: que un cambio en los documentos haga fallar un test.
- Dejar el trade-off visible (recall contra falsos positivos) y la evidencia reproducible.

**Non-Goals:**
- Cambiar el valor del umbral (se mantiene 0.64, D88) ni el modelo de embeddings.
- Búsqueda híbrida, re-ranking o reformulación de la consulta: son la mejora de fondo, pero van en otro change
  y se medirán con este mismo set.

## Decisions

1. **Dos tipos de etiqueta, verificables offline.** `covered=True` con un `term` que el documento contiene;
   `covered=False` con un `term` que ningún documento contiene. Un test recorre los `.md` fuente. Alternativa: etiquetar
   a mano sin verificación (descartada: un documento nuevo puede volver cubierto a un negativo sin que nadie lo note).
2. **Negativos en cuatro grupos.** `dominio_dificil` (20, los que más confunden), `libro_sin_resena` (10, están
   en el catálogo pero sin reseña), `ajeno` (8) y `en_negativo` (5). Medir por grupo muestra qué clase de consulta mueve el umbral.
3. **Métricas, no solo extremos.** Se barre el umbral de 0.50 a 0.90 y se reportan recall, falsos positivos,
   precisión y F1; el AUC mide la calidad del puntaje independientemente del umbral. Se proponen cuatro candidatos
   (mejor F1, Youden, recall mínimo y sin falsos positivos), cada uno responde una prioridad distinta.
4. **Los positivos son solo consultas `rag`.** Los híbridos quedan fuera: su consulta documental la redacta el modelo.
5. **`ranked()` público.** La calibración necesita el documento del primer fragmento, no solo los puntajes. Se agrega
   un método sin tocar `retrieve()`.
6. **El valor no se cambia en este change.** Con 126 consultas: AUC 0.983, documento correcto primero 98.4 %, y a 0.64
   recall 100 % con 10 de 49 falsos positivos. Mover el umbral cambia un tipo de error por otro; la decisión queda
   registrada en D97 y abierta para el equipo.

## Risks / Trade-offs

- **El set refleja los 6 documentos actuales** → al cambiar el corpus hay que recalibrar; los tests avisan si una etiqueta deja de ser válida.
- **126 consultas siguen siendo pocas para fijar un decimal** → se informa la meseta de umbrales empatados, no un único valor, y el criterio de cada candidato.
- **Los negativos «difíciles» los elegimos nosotros** → pueden ser más fáciles o más difíciles que las preguntas reales; los registros de `agent_runs` son la fuente para ampliar el set.
