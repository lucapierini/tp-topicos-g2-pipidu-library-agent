# Tasks

## 1. Traslado de artefactos

- [x] 1.1 Crear `.openspec.yaml`, `proposal.md`, `design.md` y los tres `spec.md` del change y verificar que cada requisito tiene al menos un `#### Scenario:` (R-7.x, R-8.x, R-9.x)
  _(verificado con `openspec validate --all --strict`, que exige un escenario por requisito)_
- [x] 1.2 Copiar `db/seed.sql` desde `UCSE-2026-TAIA` y verificar que su cabecera apunta a `db/schema.sql` y no al repo de origen (R-8.1)
  _(verificado en la cabecera de `db/seed.sql`, que exige `db/schema.sql` aplicado)_
- [x] 1.3 Copiar `rag/documents/*.md`, `rag/documents/pdf/*.pdf`, `rag/build_pdfs.py`, `rag/upload_to_bucket.py` y `rag/requirements.txt` y verificar que son 6 `.md` y 6 `.pdf` (R-9.1, R-9.5)
  _(verificado con `ls`: 6 `.md` en `rag/documents/` y 6 `.pdf` en `rag/documents/pdf/`)_
- [x] 1.4 Agregar `.env.local` y `.neon/` a `.gitignore` y verificar con `git check-ignore .env.local .neon/` que quedan excluidos (R-9.6)
  _(verificado: `git check-ignore` responde las dos rutas)_
- [x] 1.5 Registrar D-DB1 a D-DB10 en `TP/CHANGELOG.md` y verificar que cada fila de `design.md` tiene su entrada
  _(verificado: las 10 filas `D-DB1…D-DB10` están en la tabla del CHANGELOG, entrada del 2026-10-13)_

## 3. Verificación de documentos y bucket

- [x] 3.1 Verificar con `pypdf` que cada PDF de `rag/documents/pdf/` extrae texto y contiene el título de su `.md` (R-9.5)
  _(medido 2026-10-16 con `pypdf` sobre los 6 PDF de `rag/documents/pdf/`: cada uno extrae texto —de 1297 a 4747 caracteres— y su título aparece en el texto extraído)_

## 4. Cierre

- [x] 4.2 Correr `openspec validate --strict` y corregir lo que reporte
  _(verificado: `openspec validate --all --strict` reporta 5 changes pasados)_

## 5. Ampliación del catálogo y de las reseñas (D87)

- [x] 5.1 Ampliar `db/seed.sql` (51 libros más: cómics DC y Marvel, Empyrean, Tolkien, Narnia, Harry Potter, Berserk y Dragon Ball) con ISBN verificados en Open Library (R-8.7)
  _(verificado en `db/seed.sql`: 70 libros con ISBN-13 únicos y de dígito verificador válido, los 70 con al menos un vínculo en `libros_autores`; la verificación de cada ISBN contra Open Library es la registrada en D87)_
- [x] 5.2 Aplicarlo dos veces en la base local y verificar que la segunda no cambia filas (R-8.7)
  _(verificado en la base local; el bloque `DO $$` de `db/seed.sql` aborta si `libros` o `socios` ya tienen filas)_
- [x] 5.3 Agregar `resenas_tolkien` y `resenas_empyrean` a `rag/documents/`, y la poda de `rag/ingest.py` para los documentos que no están en la carpeta (R-9.1, R-9.7)
  _(verificado: `rag/ingest.py --dry-run` recorre los 6 documentos y da 44 fragmentos)_
