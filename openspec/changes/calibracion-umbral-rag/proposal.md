# Proposal

## Why

El umbral de similitud del RAG (`RAG_SIMILARITY_THRESHOLD`) decide qué fragmentos le llegan al modelo y cuándo el
agente responde «no encontré nada». Con pocas consultas el valor depende de 2 o 3 casos extremos (el peor caso
válido, 0.646, queda 0.003 por debajo del mejor negativo, 0.649) y no se sabe cuánto se pierde al moverlo. R-4.8
exige que el umbral esté «calibrado contra los documentos reales», pero no dice con cuántas consultas ni con qué
criterio. Además, el coseno mide cercanía temática y no que el fragmento conteste, así que conviene medir
alternativas (búsqueda híbrida y re-ranking) con el mismo método.

## What Changes

- Un set de calibración de 105 consultas etiquetadas (`tests/calibration_set.py`), que junto con las del golden
  set suma 126 (77 cubiertas por los documentos y 49 sin cobertura). Incluye los casos difíciles: preguntas del
  dominio que comparten vocabulario con los documentos, libros del catálogo sin reseña, consultas ajenas y en inglés.
- Las etiquetas se verifican sin red ni base: cada positivo lleva un término que su documento contiene y cada
  negativo uno que ningún documento contiene (`tests/test_calibration_set.py`).
- `scripts/calibrate_threshold.py` mide con curvas (recall, falsos positivos, precisión, F1), AUC, umbrales
  candidatos, resultado por grupo y precisión del documento recuperado, y guarda la evidencia.
- `RagRetriever.ranked()` expone el top-k sin umbral para medir.
- Se mide la búsqueda híbrida y el re-ranking con el mismo set y se confirman fuera de muestra con 63 consultas
  nuevas (`tests/validation_set.py`).
- El RAG usa re-ranking por defecto (`RAG_STRATEGY=rerank`, `agent/tools/reranker.py`); el umbral de coseno
  (0.64) queda como respaldo con `RAG_STRATEGY=dense` o si falla la llamada de re-ranking (R-4.11).

## Capabilities

### New Capabilities

### Modified Capabilities
- `rag-retrieval-tool`: agrega R-4.9 (método de calibración del umbral), R-4.10 (medición de alternativas) y R-4.11
  (re-ranking por defecto). Complementa R-4.8 (que el valor esté calibrado) con cómo se mide. Esta capability
  vive como delta en el change `agente-y-tools`.

## Impact

- `tests/calibration_set.py`, `tests/test_calibration_set.py`, `tests/test_calibrate_threshold.py`.
- `scripts/calibrate_threshold.py`, `scripts/evaluate_retrieval.py`, `scripts/measure_retrieval.py` y `scripts/measure_golden.py`.
- `agent/tools/rag_tool.py` (re-ranking opcional, `ranked`), `agent/tools/reranker.py`, `agent/config/__init__.py` y `.env.example`.
- `TP/evidencia/` (calibración, búsqueda híbrida y re-ranking, producción y golden set) y `TP/CHANGELOG.md` (D97 a D100).
- Sin cambios en la API, la web, la base ni Docker.
