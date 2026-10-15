# Proposal

## Why

El umbral de similitud del RAG (`RAG_SIMILARITY_THRESHOLD`) decide qué fragmentos le llegan al modelo y cuándo el
agente responde «no encontré nada». Se fijó en 0.67 con 16 consultas (D85) y bastó que entraran reseñas nuevas
(D87) para que el peor caso válido (0.646) quedara 0.003 por debajo del mejor negativo (0.649): el valor
dependía de 2 o 3 consultas extremas y no había forma de saber cuánto se perdía al moverlo. R-4.8 exige que el
umbral esté «calibrado contra los documentos reales», pero no dice con cuántas consultas ni con qué criterio.

## What Changes

- Un set de calibración de 105 consultas etiquetadas (`tests/calibration_set.py`), que junto con las del golden
  set suma 126 (77 cubiertas por los documentos y 49 sin cobertura). Incluye los casos difíciles: preguntas del
  dominio que comparten vocabulario con los documentos, libros del catálogo sin reseña, consultas ajenas y en inglés.
- Las etiquetas se verifican sin red ni base: cada positivo lleva un término que su documento contiene y cada
  negativo uno que ningún documento contiene (`tests/test_calibration_set.py`).
- `scripts/calibrate_threshold.py` mide con curvas (recall, falsos positivos, precisión, F1), AUC, umbrales
  candidatos, resultado por grupo y precisión del documento recuperado, y guarda la evidencia.
- `RagRetriever.ranked()` expone el top-k sin umbral para medir.
- No cambia el valor del umbral (0.64) ni el comportamiento del agente: es medición y criterio de decisión.

## Capabilities

### New Capabilities

### Modified Capabilities
- `rag-retrieval-tool`: agrega R-4.9, método de calibración del umbral. Complementa R-4.8 (que el valor esté calibrado)
  con cómo se mide. Hoy esta capability solo existe como delta en el change `agente-y-tools`.

## Impact

- `tests/calibration_set.py`, `tests/test_calibration_set.py`, `tests/test_calibrate_threshold.py`.
- `scripts/calibrate_threshold.py` y `agent/tools/rag_tool.py` (método `ranked`, sin cambiar `retrieve`).
- `TP/evidencia/calibracion_umbral.json` y `TP/CHANGELOG.md` (D97).
- Sin cambios en la API, la web, la base ni Docker.
