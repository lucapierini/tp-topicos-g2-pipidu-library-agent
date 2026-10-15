# Tasks

## 1. Set de calibración

- [x] 1.1 Crear `tests/calibration_set.py` con 105 consultas etiquetadas (62 cubiertas y 43 sin cobertura) en siete grupos de positivos y cuatro de negativos, cada una con un `term` verificable (R-4.9)
- [x] 1.2 Crear `tests/test_calibration_set.py`: ids y preguntas únicos, grupos con al menos 5 casos, todos los documentos cubiertos, cada positivo contiene su término en su documento, cada negativo no lo contiene en ninguno y ninguna pregunta repite las del golden set; verificar con `pytest tests/test_calibration_set.py` (R-4.9)

## 2. Medición

- [x] 2.1 Agregar `RagRetriever.ranked()` (top-k sin umbral) y reusarlo en `scores()`; verificar que `retrieve()` no cambia con `pytest tests/test_rag_tool.py` (R-4.4)
- [x] 2.2 Reescribir `scripts/calibrate_threshold.py`: barrido de umbrales (recall, falsos positivos, precisión, F1), AUC, candidatos, grupos, precisión del documento y evidencia en JSON; verificar con `pytest tests/test_calibrate_threshold.py` con casos calculados a mano (R-4.9)
- [x] 2.3 Correr la calibración contra la base local con los 6 documentos y guardar `TP/evidencia/calibracion_umbral.json` (R-4.9)

## 3. Documentación

- [x] 3.1 Registrar D97 en `TP/CHANGELOG.md` con los resultados (AUC 0.983, recall y falsos positivos por umbral) y la decisión de mantener 0.64; verificar con `openspec validate calibracion-umbral-rag --strict`

## 4. Seguimiento

- [ ] 4.1 Decidir con el equipo si se mantiene 0.64 o se pasa a 0.655 (recall 96 %, 6 falsos positivos en lugar de 10) (R-4.8)
- [ ] 4.2 Probar búsqueda híbrida (embeddings + palabras exactas) o re-ranking y medirlos con este mismo set: el objetivo es subir el AUC y bajar los falsos positivos sin perder recall (R-4.9)
- [ ] 4.3 Ampliar los negativos con consultas reales de `agent_runs` clasificadas `rag` sin documento relevante (R-4.9)

## Workflow follow-up

- Archivar `agente-y-tools` primero (R-4.9 se agrega sobre su spec de `rag-retrieval-tool`) y después este change.
