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
- Adoptar búsqueda híbrida o re-ranking en `retrieve()`: se **miden** acá (R-4.10, D98) pero el equipo decide después,
  con consultas nuevas. La reformulación de la consulta sigue fuera.

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

**Pendiente de la cuota diaria.** La corrida se cortó con 429 (`generate_content` 500/día y `embed_content` 1.000/día
agotadas; se renuevan en unas 23 h). Hay re-ranking cacheado para 46 de las 63 consultas de validación; los vectores no se
guardaban, así que el resto se completa en la próxima corrida:
`python scripts/evaluate_retrieval.py` (retoma desde los cachés). Los números de la sección anterior siguen siendo de calibración.

## Risks / Trade-offs

- **El set refleja los 6 documentos actuales** → al cambiar el corpus hay que recalibrar; los tests avisan si una etiqueta deja de ser válida.
- **126 consultas siguen siendo pocas para fijar un decimal** → se informa la meseta de umbrales empatados, no un único valor, y el criterio de cada candidato.
- **α, el rango de normalización y el umbral de cada estrategia se eligieron sobre este mismo set** → los números están optimistas; adoptar una estrategia exige confirmarla con consultas no vistas.
- **El re-ranking suma una llamada al modelo por consulta** (latencia y cuota) y su calidad depende de un prompt y de un modelo → hay que decidir si el costo vale la mejora; el híbrido no cuesta llamadas.
- **Los negativos «difíciles» los elegimos nosotros** → pueden ser más fáciles o más difíciles que las preguntas reales; los registros de `agent_runs` son la fuente para ampliar el set.
