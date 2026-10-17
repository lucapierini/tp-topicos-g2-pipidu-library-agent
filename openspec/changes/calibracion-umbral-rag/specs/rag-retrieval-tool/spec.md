# Spec Delta

## ADDED Requirements

### Requirement: R-4.9 — Calibración del umbral con un set etiquetado y verificable
El umbral de similitud SHALL calibrarse con un set de al menos 50 consultas con cobertura y 30 sin cobertura, cada una etiquetada y verificable contra los documentos fuente sin red ni base. La calibración SHALL informar, para cada umbral, el recall sobre las consultas cubiertas y los falsos positivos sobre las no cubiertas, y SHALL guardar la evidencia.

#### Scenario: etiqueta verificable de una consulta cubierta
- **GIVEN** una consulta del set marcada como cubierta por un documento
- **WHEN** se ejecutan los tests del set
- **THEN** el documento fuente contiene el término que justifica la etiqueta
- **AND** si el término desaparece el test falla y avisa que la consulta ya no está cubierta

#### Scenario: etiqueta verificable de una consulta sin cobertura
- **GIVEN** una consulta del set marcada como sin cobertura
- **WHEN** se ejecutan los tests del set
- **THEN** su término clave no aparece en ningún documento
- **AND** si un documento nuevo lo incorpora el test falla y avisa que ya no es un negativo

#### Scenario: cobertura del set
- **WHEN** se ejecutan los tests del set
- **THEN** todos los documentos ingestados tienen al menos una consulta cubierta
- **AND** cada grupo (reglamento, políticas, cada reseña, inglés, dominio difícil, libros sin reseña, ajenas) tiene al menos 5 consultas

#### Scenario: calibración con el set completo
- **GIVEN** la base con los documentos indexados
- **WHEN** se ejecuta `scripts/calibrate_threshold.py`
- **THEN** informa por umbral el recall, los falsos positivos, la precisión y el F1
- **AND** informa el AUC de la similitud y el resultado por grupo de consultas
- **AND** informa si el primer fragmento recuperado es del documento esperado
- **AND** guarda la evidencia en `TP/evidencia/calibracion_umbral.json`

#### Scenario: grupos que se solapan
- **GIVEN** que la similitud más baja de una consulta cubierta es menor que la más alta de una no cubierta
- **WHEN** se ejecuta la calibración
- **THEN** informa que ningún umbral separa los grupos y muestra el costo de cada candidato (recall y falsos positivos)
- **AND** el valor configurado queda registrado en `TP/CHANGELOG.md` con esa evidencia

### Requirement: R-4.10 — Evaluación de estrategias de recuperación con el mismo set
Antes de cambiar la estrategia de recuperación (búsqueda híbrida o re-ranking), el sistema SHALL medirla con el set de calibración de R-4.9 y SHALL compararla con la similitud de coseno actual usando las mismas métricas (AUC, F1, recall y falsos positivos), sin modificar `retrieve()` hasta que el equipo decida adoptarla.

#### Scenario: comparación de estrategias
- **GIVEN** la base con los documentos indexados y el set de calibración
- **WHEN** se ejecuta `scripts/evaluate_retrieval.py`
- **THEN** informa para cada estrategia (denso, léxico, híbrido con distintos pesos, re-ranking y sus combinaciones) el AUC, el mejor F1 y los falsos positivos al mantener un recall del 95 %
- **AND** informa en cuántas consultas cubiertas el primer fragmento es del documento esperado
- **AND** guarda la evidencia en `TP/evidencia/busqueda_hibrida_rerank.json`

#### Scenario: validación fuera de muestra
- **GIVEN** un set de validación con al menos 25 consultas con cobertura y 25 sin cobertura, distinto del de calibración y sin preguntas en común
- **WHEN** se ejecuta `scripts/evaluate_retrieval.py`
- **THEN** los parámetros de cada estrategia (peso del híbrido, rango de normalización y umbrales) se eligen solo con el set de calibración
- **AND** se aplican sin reajustarse al set de validación
- **AND** se informan el AUC, el recall y los falsos positivos de cada estrategia sobre el set de validación junto a los de calibración

#### Scenario: set de validación verificable
- **WHEN** se ejecutan los tests del set de validación
- **THEN** cada positivo contiene su término en su documento y cada negativo no lo contiene en ninguno
- **AND** ninguna pregunta se repite con el set de calibración ni con el golden set

#### Scenario: repetir la medición sin gastar cuota
- **GIVEN** una evaluación ya ejecutada
- **WHEN** se vuelve a ejecutar
- **THEN** los vectores de las consultas y los puntajes del re-ranking salen de un caché local y no se vuelve a llamar a la API
- **AND** un caché de otro modelo de embeddings o de otra dimensión no se reutiliza

#### Scenario: puntaje léxico
- **GIVEN** una consulta con un término que no existe en ningún documento
- **WHEN** se calcula la cobertura léxica
- **THEN** ese término pesa el máximo en el denominador y baja la cobertura aunque el resto de la consulta coincida

#### Scenario: puntaje híbrido
- **WHEN** se combinan la similitud normalizada y la cobertura léxica con un peso `alpha`
- **THEN** el puntaje de la consulta es el del mejor fragmento entre todos los del corpus
- **AND** `alpha = 1` equivale a la similitud densa

#### Scenario: re-ranking sin red en los tests
- **GIVEN** un cliente de modelo simulado
- **WHEN** se puntúan los fragmentos candidatos
- **THEN** la salida inválida (cantidad distinta de puntajes, no JSON, valores no numéricos) se rechaza
- **AND** los puntajes se acotan a 0..3
- **AND** el resultado de cada consulta se guarda para no repetir la llamada al modelo

#### Scenario: costo declarado
- **WHEN** se informa una estrategia que usa el modelo
- **THEN** la evidencia indica cuántas llamadas adicionales por consulta requiere

### Requirement: R-4.11 — Recuperación con re-ranking
La herramienta de recuperación SHALL, con la estrategia `rerank` (por defecto), pedir al modelo que puntúe de 0 a 3 si cada uno de los fragmentos candidatos contiene la respuesta a la consulta, SHALL aceptar la consulta solo si el puntaje combinado (0.7 por la mejor relevancia normalizada más 0.3 por la mejor similitud de coseno normalizada) alcanza `RAG_RERANK_THRESHOLD`, y SHALL devolver únicamente los fragmentos con relevancia 1 o más, de mayor a menor relevancia y similitud.

#### Scenario: la similitud alta no alcanza si ningún fragmento contesta
- **GIVEN** una consulta cuyo mejor fragmento tiene similitud de coseno 0.70 pero a la que el modelo da relevancia 0 en todos los candidatos
- **WHEN** se recuperan documentos
- **THEN** el resultado es `NO_RELEVANT_RESULTS`

#### Scenario: la similitud baja no descarta una respuesta presente
- **GIVEN** una consulta cuyo mejor fragmento tiene similitud 0.55 y a la que el modelo da relevancia 3
- **WHEN** se recuperan documentos
- **THEN** se devuelve ese fragmento, con su similitud de coseno como evidencia

#### Scenario: el modelo falla
- **GIVEN** que la llamada de re-ranking falla (cuota, red, salida inválida o cantidad de puntajes distinta)
- **WHEN** se recuperan documentos
- **THEN** esa consulta se resuelve con el umbral de coseno `RAG_SIMILARITY_THRESHOLD`
- **AND** el fallo se registra en el log y la consulta no falla

#### Scenario: estrategia de solo coseno
- **GIVEN** `RAG_STRATEGY=dense` o ninguna instancia de re-ranker
- **WHEN** se recuperan documentos
- **THEN** no se llama al modelo y el comportamiento es el del umbral de coseno (R-4.4)

#### Scenario: costo declarado
- **WHEN** la estrategia es `rerank`
- **THEN** cada recuperación suma una llamada al modelo con temperatura 0 y salida estructurada validada
- **AND** una consulta sin candidatos o vacía no llama al modelo

#### Scenario: medición del código de producción
- **WHEN** se ejecuta `scripts/measure_retrieval.py`
- **THEN** informa para `retrieve()` con cada estrategia, sobre los sets de calibración y de validación, el recall, los falsos positivos, la precisión, el F1, el documento del primer fragmento y la latencia
- **AND** informa cuántas llamadas al re-ranker hubo y cuántas fallaron

#### Scenario: aceptación con el RAG real
- **GIVEN** la base con el catálogo y los documentos ingestados
- **WHEN** se ejecuta `scripts/measure_golden.py --db --rag-real` dentro de la imagen del agente
- **THEN** el golden set conserva la clasificación correcta en al menos 11 de 13 casos (R-2.1)
- **AND** se evalúa el contenido de los casos SQL, RAG e híbridos contra las fuentes reales
- **AND** la evidencia indica la estrategia de recuperación y sus umbrales

