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
- La búsqueda híbrida no se adopta (queda medida): el re-ranking la supera fuera de muestra. La reformulación de la
  consulta sigue fuera.

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

7. **Se evalúan puntajes alternativos, no una nueva arquitectura.** `scripts/evaluate_retrieval.py` calcula, sobre las
   mismas 126 consultas y con las mismas métricas, el puntaje de cada estrategia sobre *todos* los fragmentos (el
   corpus tiene 44), sin modificar `retrieve()`.
8. **Léxico: cobertura IDF, no BM25 crudo.** BM25 no tiene escala fija y no se puede cortar con un umbral. La cobertura
   (fracción del peso IDF de la consulta presente en el fragmento) va de 0 a 1 y castiga lo que buscamos: un término
   que no existe en ningún documento («wifi») pesa lo máximo y no se cubre. Raíz tosca de 6 caracteres y sin acentos,
   sin dependencias. Con una base grande correspondería `tsvector` de PostgreSQL.
9. **Híbrido: combinación lineal con el coseno normalizado a [0.50, 0.85].** Se prueba `α ∈ {0.5…0.9}`. RRF no sirve porque
   no da un puntaje absoluto para cortar (hay que poder decir «no hay nada»).
10. **Re-ranking: el modelo juzga si el fragmento *contiene la respuesta*.** Escala 0–3 con una consigna que dice que
    compartir tema o vocabulario no pasa de 1; una llamada por consulta con los 5 candidatos, temperatura 0 y salida
    estructurada validada. Los resultados se guardan en un caché para que la medición sea repetible y barata. Se
    prueba solo, combinado con el coseno (el coseno desempata) y sobre los candidatos del híbrido.
11. **Reintento ante 5xx.** `call_with_retry` solo cubre la cuota (429); la medición cayó por un 503 de alta demanda, así que
    el re-ranker reintenta 5xx con backoff y no reintenta errores de cliente.
12. **Validación fuera de muestra (D99).** `tests/validation_set.py` suma 63 consultas nuevas (35 con cobertura y 28 sin ella), escritas
    como las escribe un socio (coloquiales, con contexto personal, parafraseadas) y verificables con la misma regla de términos.
    Los parámetros se congelan con el set de calibración (`alpha` de mayor AUC, rango de normalización y los umbrales de mejor F1
    y de recall ≥ 95 %) y se aplican **sin reajustar** al de validación; la diferencia entre los dos mide cuánto sobreestimaba la
    calibración. Un test impide que una pregunta esté en los dos sets.
13. **Caché local de vectores de consulta.** Cada corrida repetía ~190 llamadas de embedding y agotó la cuota gratuita diaria
    (1.000 por día) junto con la de generación (500 por día). `CachedEmbedder` guarda cada vector en `.cache/` (fuera de git) apenas
    se obtiene, con el modelo y la dimensión en la clave, así que un corte de cuota no pierde lo hecho.

## Results (D98)

Sobre 77 consultas cubiertas y 49 sin cobertura:

| Estrategia | AUC | Mejor F1 | Con recall ≥ 95 % |
|---|---|---|---|
| Coseno (actual) | 0.983 | 0.951 (8 falsos positivos) | 6 falsos positivos |
| Léxico solo | 0.879 | 0.883 | no sirve |
| Híbrido α=0.8 | 0.988 | 0.968 | 3 falsos positivos, recall 97 % |
| Re-ranking solo | 0.976 | 0.946 | 8 falsos positivos, recall 99 % |
| Re-ranking + coseno | 0.994 | 0.987 | 1 falso positivo, recall 97–99 % |
| Híbrido + re-ranking + coseno | 0.993 | 0.981 | 2 falsos positivos, recall 97 % |

Lectura: el léxico solo es malo (no entiende el inglés ni los sinónimos) pero **aporta una señal que el coseno no tiene**:
combinado baja los falsos positivos a la mitad sin costo de modelo. El re-ranking es lo único que ataca el problema de
fondo —juzgar si el fragmento *contesta*—: 41 de 49 consultas sin cobertura reciben 0 y solo una recibe 3. Solo, empata
mucho (4 valores), y por eso el coseno como desempate lo lleva a AUC 0.994. Los pocos errores que quedan son dos consultas
en inglés y una definición; el falso positivo («descuentos en las multas para docentes») tiene una etiqueta discutible.

### Validación fuera de muestra (D99)

Los parámetros se eligieron con las 126 consultas de calibración y se aplicaron sin reajustar a 63 consultas nuevas
(35 con cobertura y 28 sin ella, redactadas de forma coloquial y parafraseada):

| Estrategia | AUC calibración | AUC validación | Falsos positivos validación (umbral de mejor F1) | F1 validación |
|---|---|---|---|---|
| Coseno (actual) | 0.983 | **0.912** | 9/28 | 0.84 |
| Híbrido α=0.8 | 0.988 | 0.941 | 5/28 | 0.87 |
| Re-ranking solo | 0.976 | 0.976 | 1/28 | 0.94 |
| **Re-ranking + coseno** | 0.994 | **0.986** | **3/28 (1/28 con recall ≥ 95 %)** | **0.93 (0.96)** |

Lectura: **la calibración sobreestimaba el coseno** —las preguntas coloquiales lo castigan más (AUC 0.983 → 0.912)— y la mejora
del híbrido se reduce a la mitad. El re-ranking prácticamente no pierde: juzga si el fragmento contesta, y eso no depende de cómo
se redacte la pregunta. Es lo único que se sostiene fuera de muestra.

### Código de producción medido (D100)

`scripts/measure_retrieval.py` ejecuta `RagRetriever.retrieve()` real (umbral de re-ranking 0.40, coseno 0.64):

| Conjunto / estrategia | Recall | Perdidas | Falsos positivos | F1 | Mediana | p95 |
|---|---|---|---|---|---|---|
| Calibración / coseno | 1.00 | 0/77 | 10/49 | 0.94 | 1 ms | 2 ms |
| Calibración / re-ranking | 0.97 | 2/77 | 1/49 | 0.98 | 893 ms | 1087 ms |
| Validación / coseno | 0.91 | 3/35 | **13/28** | 0.80 | 2 ms | 3 ms |
| Validación / re-ranking | 0.94 | 2/35 | **1/28** | 0.96 | 881 ms | 977 ms |

189 llamadas al re-ranker, ninguna fallida. El costo es **~0.9 s más por consulta documental**. Quedan 2 perdidas en cada set
(«qué son los code smells», «who wrote One Hundred Years of Solitude?», «qué es un apercibimiento», «batalla de los Campos del
Pelennor»: el fragmento está en el top-5 pero el modelo no lo puntúa como respuesta) y 1 falso positivo en cada uno («descuentos
en las multas para docentes», «los docentes pagan la mitad de multa»), que son los casos donde el reglamento sí dice que la
multa es igual para todos, así que la etiqueta es discutible.

15. **Se adopta el re-ranking (D100).** `retrieve()` usa por defecto `RAG_STRATEGY=rerank`: el modelo puntúa los 5 candidatos del
    coseno y el corte usa el puntaje combinado (umbral 0.40). Devuelve los fragmentos con relevancia ≥ 1 ordenados por relevancia
    y similitud. Si la llamada falla, la consulta vuelve al coseno. `RAG_STRATEGY=dense` conserva el comportamiento anterior.

## Risks / Trade-offs

- **El set refleja los 6 documentos actuales** → al cambiar el corpus hay que recalibrar; los tests avisan si una etiqueta deja de ser válida.
- **126 consultas siguen siendo pocas para fijar un decimal** → se informa la meseta de umbrales empatados, no un único valor, y el criterio de cada candidato.
- **α, el rango de normalización y el umbral se eligieron con el set de calibración** → se confirmaron fuera de muestra (D99): el coseno se degradó y el re-ranking no. El 0.40 sale de la calibración y se mantuvo para la validación.
- **El re-ranking suma ~0.9 s y una llamada al modelo por consulta documental** y depende de la cuota → si falla, esa consulta vuelve al coseno (R-4.11); `RAG_STRATEGY=dense` lo desactiva. El prompt y el modelo se midieron juntos: cambiar de modelo exige repetir `measure_retrieval.py`.
- **Los negativos «difíciles» los elegimos nosotros** → pueden ser más fáciles o más difíciles que las preguntas reales; los registros de `agent_runs` son la fuente para ampliar el set.
