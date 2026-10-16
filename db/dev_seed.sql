-- Datos de DESARROLLO para probar el agente contra una base real (no es el seed entregable, T2.4).
--
-- Son pocas filas, deterministas y con fechas relativas a CURRENT_DATE: "vencido", "hace 20 días" y
-- "este cuatrimestre" dan resultados reproducibles sin importar cuándo se levante la base. Las fechas
-- se fijan al cargar: la base envejece un día por día y los atrasos crecen. Para volver a la foto de
-- hoy, truncar las tablas del dominio y recargar este archivo (no asertar días de atraso literales).
-- Contiene las entidades que nombra el golden set (`tests/golden_set.py::SEED_ENTITIES`).
--
-- El volumen exigido (>= 15 por tabla, T2.5) y la semilla fija los entrega `db/seed_data.py` (pendiente, T2.4):
-- este archivo llega a 3-11 filas por tabla, así que 2.5 sigue abierta. Esto solo existe para poder correr
-- `pytest -m integration` y `scripts/measure_golden.py --db`.

INSERT INTO categorias (nombre, descripcion) VALUES
  ('Ciencias de la Computación', 'Informática, sistemas y redes'),
  ('Literatura', 'Narrativa y poesía'),
  ('Historia', 'Historia argentina y universal');

INSERT INTO editoriales (nombre, pais) VALUES
  ('Sudamericana', 'Argentina'),
  ('Alfa', 'España'),
  ('Pearson', 'Estados Unidos');

INSERT INTO autores (nombre, apellido, nacionalidad, fecha_nacimiento) VALUES
  ('Gabriel', 'García Márquez', 'Colombiana', '1927-03-06'),
  ('Julio', 'Cortázar', 'Argentina', '1914-08-26'),
  ('Jorge Luis', 'Borges', 'Argentina', '1899-08-24'),
  ('Andrew', 'Tanenbaum', 'Estadounidense', '1944-03-16'),
  ('Herbert', 'Bos', 'Neerlandesa', '1970-01-01'),
  ('Félix', 'Luna', 'Argentina', '1925-09-30');

INSERT INTO libros (titulo, isbn, editorial_id, categoria_id, anio_publicacion, ejemplares_totales, ejemplares_disponibles) VALUES
  ('Cien años de soledad', '978-0-00-000001-1',
     (SELECT id FROM editoriales WHERE nombre = 'Sudamericana'),
     (SELECT id FROM categorias WHERE nombre = 'Literatura'), 1967, 4, 2),
  ('Rayuela', '978-0-00-000002-2',
     (SELECT id FROM editoriales WHERE nombre = 'Sudamericana'),
     (SELECT id FROM categorias WHERE nombre = 'Literatura'), 1963, 3, 2),
  ('Ficciones', '978-0-00-000003-3',
     (SELECT id FROM editoriales WHERE nombre = 'Sudamericana'),
     (SELECT id FROM categorias WHERE nombre = 'Literatura'), 1944, 2, 2),
  ('El Aleph', '978-0-00-000004-4',
     (SELECT id FROM editoriales WHERE nombre = 'Alfa'),
     (SELECT id FROM categorias WHERE nombre = 'Literatura'), 1949, 2, 2),
  ('Sistemas Operativos Modernos', '978-0-00-000005-5',
     (SELECT id FROM editoriales WHERE nombre = 'Pearson'),
     (SELECT id FROM categorias WHERE nombre = 'Ciencias de la Computación'), 2015, 5, 3),
  ('Redes de Computadoras', '978-0-00-000006-6',
     (SELECT id FROM editoriales WHERE nombre = 'Pearson'),
     (SELECT id FROM categorias WHERE nombre = 'Ciencias de la Computación'), 2012, 4, 4),
  ('Historia de los argentinos', '978-0-00-000007-7',
     (SELECT id FROM editoriales WHERE nombre = 'Alfa'),
     (SELECT id FROM categorias WHERE nombre = 'Historia'), 1993, 3, 3);

-- N:M libro <-> autor. "Sistemas Operativos Modernos" tiene dos autores.
INSERT INTO libros_autores (libro_id, autor_id, orden) VALUES
  ((SELECT id FROM libros WHERE titulo = 'Cien años de soledad'),
   (SELECT id FROM autores WHERE apellido = 'García Márquez'), 1),
  ((SELECT id FROM libros WHERE titulo = 'Rayuela'),
   (SELECT id FROM autores WHERE apellido = 'Cortázar'), 1),
  ((SELECT id FROM libros WHERE titulo = 'Ficciones'),
   (SELECT id FROM autores WHERE apellido = 'Borges'), 1),
  ((SELECT id FROM libros WHERE titulo = 'El Aleph'),
   (SELECT id FROM autores WHERE apellido = 'Borges'), 1),
  ((SELECT id FROM libros WHERE titulo = 'Sistemas Operativos Modernos'),
   (SELECT id FROM autores WHERE apellido = 'Tanenbaum'), 1),
  ((SELECT id FROM libros WHERE titulo = 'Sistemas Operativos Modernos'),
   (SELECT id FROM autores WHERE apellido = 'Bos'), 2),
  ((SELECT id FROM libros WHERE titulo = 'Redes de Computadoras'),
   (SELECT id FROM autores WHERE apellido = 'Tanenbaum'), 1),
  ((SELECT id FROM libros WHERE titulo = 'Historia de los argentinos'),
   (SELECT id FROM autores WHERE apellido = 'Luna'), 1);

INSERT INTO socios (nombre, apellido, legajo, tipo_socio, email, fecha_alta) VALUES
  ('Juan', 'Pérez', 'A-1001', 'alumno', 'juan.perez@uni.example', CURRENT_DATE - 400),
  ('Ana', 'Gómez', 'A-1002', 'alumno', 'ana.gomez@uni.example', CURRENT_DATE - 300),
  ('Pedro', 'Ruiz', 'A-1003', 'alumno', 'pedro.ruiz@uni.example', CURRENT_DATE - 200),
  ('Luis', 'Martínez', 'D-2001', 'docente', 'luis.martinez@uni.example', CURRENT_DATE - 900),
  ('María', 'López', 'D-2002', 'docente', 'maria.lopez@uni.example', CURRENT_DATE - 700),
  ('Sofía', 'Díaz', 'A-1004', 'alumno', 'sofia.diaz@uni.example', CURRENT_DATE - 100);  -- sin préstamos (R-3.8)

-- Préstamos (fechas relativas a hoy).
--   * Juan Pérez: 'Cien años de soledad' hace 20 días, plazo de 15 -> VENCIDO hace 5 días (G3, G10).
--   * Juan Pérez: 'Rayuela' hace 3 días -> ACTIVO.
--   * Pedro Ruiz: 'Sistemas Operativos Modernos' hace 35 días -> VENCIDO hace 20 días (G3).
--   * El resto devueltos, para los rankings (G2) y el socio con más préstamos (G11).
INSERT INTO prestamos (libro_id, socio_id, fecha_prestamo, fecha_devolucion_prevista, fecha_devolucion_real, estado) VALUES
  ((SELECT id FROM libros WHERE titulo = 'Cien años de soledad'),
   (SELECT id FROM socios WHERE legajo = 'A-1001'), CURRENT_DATE - 20, CURRENT_DATE - 5, NULL, 'activo'),
  ((SELECT id FROM libros WHERE titulo = 'Rayuela'),
   (SELECT id FROM socios WHERE legajo = 'A-1001'), CURRENT_DATE - 3, CURRENT_DATE + 12, NULL, 'activo'),
  ((SELECT id FROM libros WHERE titulo = 'Sistemas Operativos Modernos'),
   (SELECT id FROM socios WHERE legajo = 'A-1003'), CURRENT_DATE - 35, CURRENT_DATE - 20, NULL, 'activo'),
  ((SELECT id FROM libros WHERE titulo = 'Cien años de soledad'),
   (SELECT id FROM socios WHERE legajo = 'A-1002'), CURRENT_DATE - 60, CURRENT_DATE - 45, CURRENT_DATE - 47, 'devuelto'),
  ((SELECT id FROM libros WHERE titulo = 'Cien años de soledad'),
   (SELECT id FROM socios WHERE legajo = 'D-2001'), CURRENT_DATE - 50, CURRENT_DATE - 20, CURRENT_DATE - 25, 'devuelto'),
  ((SELECT id FROM libros WHERE titulo = 'Cien años de soledad'),
   (SELECT id FROM socios WHERE legajo = 'D-2002'), CURRENT_DATE - 40, CURRENT_DATE - 10, CURRENT_DATE - 12, 'devuelto'),
  ((SELECT id FROM libros WHERE titulo = 'Ficciones'),
   (SELECT id FROM socios WHERE legajo = 'A-1002'), CURRENT_DATE - 30, CURRENT_DATE - 15, CURRENT_DATE - 16, 'devuelto'),
  ((SELECT id FROM libros WHERE titulo = 'Ficciones'),
   (SELECT id FROM socios WHERE legajo = 'D-2001'), CURRENT_DATE - 25, CURRENT_DATE - 10, CURRENT_DATE - 10, 'devuelto'),
  ((SELECT id FROM libros WHERE titulo = 'Redes de Computadoras'),
   (SELECT id FROM socios WHERE legajo = 'D-2001'), CURRENT_DATE - 18, CURRENT_DATE - 3, CURRENT_DATE - 5, 'devuelto'),
  ((SELECT id FROM libros WHERE titulo = 'Rayuela'),
   (SELECT id FROM socios WHERE legajo = 'D-2001'), CURRENT_DATE - 12, CURRENT_DATE + 3, CURRENT_DATE - 2, 'devuelto'),
  ((SELECT id FROM libros WHERE titulo = 'El Aleph'),
   (SELECT id FROM socios WHERE legajo = 'A-1002'), CURRENT_DATE - 9, CURRENT_DATE + 6, CURRENT_DATE - 1, 'devuelto');
