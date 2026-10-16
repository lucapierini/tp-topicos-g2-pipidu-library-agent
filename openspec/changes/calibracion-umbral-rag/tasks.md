# Tasks

## 1. Set de calibración

- [x] 1.1 Crear `tests/calibration_set.py` con 105 consultas etiquetadas (62 cubiertas y 43 sin cobertura) en siete grupos de positivos y cuatro de negativos, cada una con un `term` verificable (R-4.9)
- [x] 1.2 Crear `tests/test_calibration_set.py`: ids y preguntas únicos, grupos con al menos 5 casos, todos los documentos cubiertos, cada positivo contiene su término en su documento, cada negativo no lo contiene en ninguno y ninguna pregunta repite las del golden set; verificar con `pytest tests/test_calibration_set.py` (R-4.9)

## 2. Medición

- [x] 2.1 Agregar `RagRetriever.ranked()` (top-k sin umbral) y reusarlo en `scores()`; verificar que `retrieve()` no cambia con `pytest tests/test_rag_tool.py` (R-4.4)
- [x] 2.2 Reescribir `scripts/calibrate_threshold.py`: barrido de umbrales (recall, falsos positivos, precisión, F1), AUC, candidatos, grupos, precisión del documento y evidencia en JSON; verificar con `pytest tests/test_calibrate_threshold.py` con casos calculados a mano (R-4.9)
- [x] 2.3 Correr la calibración contra la base local con los 6 documentos y guardar `TP/evidencia/calibracion_umbral.json` (R-4.9)

## 3. Evaluación de búsqueda híbrida y re-ranking

- [x] 3.1 Crear `scripts/evaluate_retrieval.py`: tokenización, cobertura IDF, combinación híbrida, re-ranking con el modelo (caché, validación de la salida, reintento ante 5xx) y resumen por estrategia con AUC, F1, falsos positivos y documento correcto; verificar con `pytest tests/test_evaluate_retrieval.py` sobre dobles (R-4.10)
- [x] 3.2 Correr la evaluación contra la base local y guardar `TP/evidencia/busqueda_hibrida_rerank.json` y el caché `rerank_scores.json` (R-4.10)

## 3b. Validación fuera de muestra

- [x] 3b.1 Crear `tests/validation_set.py` con 63 consultas nuevas (35 con cobertura, 28 sin ella) y `tests/test_validation_set.py`: términos verificables en los documentos y ninguna pregunta repetida con calibración ni con el golden set; verificar con `pytest tests/test_validation_set.py` (R-4.10)
- [x] 3b.2 Congelar los parámetros con la calibración y aplicarlos al set de validación (`frozen_thresholds`, `validate`, `choose_alpha`) con tests (R-4.10)
- [x] 3b.3 Agregar `CachedEmbedder` (vectores de consulta en `.cache/`, con el modelo y la dimensión en la clave) para no gastar cuota al repetir la medición (R-4.10)
- [ ] 3b.4 Ejecutar `python scripts/evaluate_retrieval.py` con la cuota diaria de Gemini renovada y guardar la sección `validation` de `TP/evidencia/busqueda_hibrida_rerank.json`; completar los resultados fuera de muestra en `design.md` y en D99 (R-4.10)

## 4. Documentación

- [x] 4.1 Registrar D97 en `TP/CHANGELOG.md` con los resultados (AUC 0.983, recall y falsos positivos por umbral) y la decisión de mantener 0.64; verificar con `openspec validate calibracion-umbral-rag --strict`
- [x] 4.2 Registrar D98 con los resultados de híbrido y re-ranking y actualizar la spec (R-4.10)

## 5. Seguimiento

- [ ] 5.1 Decidir con el equipo si se mantiene 0.64 o se pasa a 0.655 (recall 96 %, 6 falsos positivos en lugar de 10) (R-4.8)
- [ ] 5.2 Revisar los resultados fuera de muestra (3b.4) contra los de calibración (re-ranking + coseno: AUC 0.994, 1 falso positivo; híbrido α=0.8: 3 falsos positivos) y decidir si la mejora se sostiene (R-4.10)
- [ ] 5.3 Si se confirma, implementar la estrategia elegida en `retrieve()` detrás de una variable de configuración, con tests y la latencia extra medida; decidir entre re-ranking (1 llamada más por consulta) e híbrido (sin llamadas) (R-4.4, R-4.10)
- [ ] 5.4 Ampliar los negativos con consultas reales de `agent_runs` clasificadas `rag` sin documento relevante (R-4.9)

## Workflow follow-up

- Archivar `agente-y-tools` primero (R-4.9 se agrega sobre su spec de `rag-retrieval-tool`) y después este change.
