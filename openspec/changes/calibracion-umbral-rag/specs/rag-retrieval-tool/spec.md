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
