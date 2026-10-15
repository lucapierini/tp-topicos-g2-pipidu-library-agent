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
