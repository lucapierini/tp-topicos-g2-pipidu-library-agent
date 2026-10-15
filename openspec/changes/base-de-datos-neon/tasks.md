# Tasks

## 1. Traslado de artefactos

- [x] 1.1 Crear `.openspec.yaml`, `proposal.md`, `design.md` y los tres `spec.md` del change y verificar que cada requisito tiene al menos un `#### Scenario:` (R-7.x, R-8.x, R-9.x)
- [x] 1.2 Copiar `db/seed.sql` desde `UCSE-2026-TAIA` y verificar que su cabecera apunta a `db/schema.sql` y no al repo de origen (R-8.1)
- [x] 1.3 Copiar `rag/documents/*.md`, `rag/documents/pdf/*.pdf`, `rag/build_pdfs.py`, `rag/upload_to_bucket.py` y `rag/requirements.txt` y verificar que son 6 `.md` y 6 `.pdf` (R-9.1, R-9.5)
- [x] 1.4 Agregar `.env.local` y `.neon/` a `.gitignore` y verificar con `git check-ignore .env.local .neon/` que quedan excluidos (R-9.6)
- [x] 1.5 Registrar D-DB1 a D-DB10 en `TP/CHANGELOG.md` y verificar que cada fila de `design.md` tiene su entrada

## 2. Verificación contra el esquema

- [ ] 2.1 Aplicar `db/schema.sql` y `db/seed.sql` en una base local limpia y verificar que el seed termina sin errores y que `SELECT count(*)` da ≥ 15 en las 7 tablas de dominio (R-8.1, R-8.5)
- [ ] 2.2 Verificar que `v_prestamos_estado` devuelve al menos un préstamo `vencido` tras cargar el seed (R-8.2, R-7.5)
- [ ] 2.3 Verificar que una segunda aplicación del seed aborta sin cambiar filas (R-8.6)
- [ ] 2.4 Verificar que los títulos reseñados existen en `libros` (R-8.3)
- [ ] 2.5 Verificar con `pytest -m integration` los CHECK de R-7.4 y R-7.6, la dimensión de R-7.8 y los permisos de R-7.9 (hoy cubiertos por `tests/test_runs_integration.py` y los tests de integración existentes; agregar los que falten)

## 3. Verificación de documentos y bucket

- [ ] 3.1 Verificar con `pypdf` que cada PDF de `rag/documents/pdf/` extrae texto y contiene el título de su `.md` (R-9.5)
- [ ] 3.2 Revisar a mano que las políticas no contradicen al reglamento y dejar el resultado en `TP/CHANGELOG.md` (R-9.3)
- [ ] 3.3 Cruzar los casos RAG e híbridos de `tests/golden_set.py` con los documentos y verificar que cada uno tiene un fragmento fuente (R-9.7)
- [ ] 3.4 Ejecutar `python rag/upload_to_bucket.py` dos veces con `.env.local` y verificar que el bucket `rag` queda con 6 objetos bajo `documents/` (R-9.6). Requiere las credenciales de Neon

## 4. Cierre

- [ ] 4.1 Actualizar `agente-y-tools/tasks.md` marcando 2.5, 2.7 y 3.1 si 2.1 y 3.1 de este change pasan, y 9.6 con la decisión D-DB1
- [x] 4.2 Correr `openspec validate --strict` y corregir lo que reporte
- [ ] 4.3 Archivar con `openspec archive base-de-datos-neon` cuando 2.x y 3.x estén completas

## 5. Ampliación del catálogo y de las reseñas (D77)

- [x] 5.1 Ampliar `db/seed.sql` (51 libros más: cómics DC y Marvel, Empyrean, Tolkien, Narnia, Harry Potter, Berserk y Dragon Ball) con ISBN verificados en Open Library (R-8.7)
- [x] 5.2 Aplicarlo dos veces en la base local y verificar que la segunda no cambia filas (R-8.7)
- [x] 5.3 Reemplazar la reseña de IA por `resenas_tolkien` y `resenas_empyrean`, y agregar la poda a `rag/ingest.py` (R-9.1, R-9.7)
- [ ] 5.4 Aplicar la ampliación y la ingesta en Neon, y reflejar los cambios en el bucket `rag`

## Workflow follow-up

- Aplicar R-7.9 en la base de Neon (login del rol de solo lectura) está en `agente-y-tools` 9.7.
- El seed con semilla fija (`db/seed_data.py`, `agente-y-tools` 2.4) sigue pendiente: este change aporta un seed SQL estático.
