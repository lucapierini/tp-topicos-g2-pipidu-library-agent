-- =============================================================================
-- Pipidu Library Agent — Seed de datos (change base-de-datos-neon)
-- Catálogo REAL (70 libros: títulos, autores, editoriales, ISBN verificados en Open Library).
-- Socios y préstamos SINTÉTICOS. Fechas de préstamos relativas a CURRENT_DATE,
-- así siempre hay préstamos activos y vencidos.
-- Requiere db/schema.sql aplicado (más sus roles/permisos si corre en una base local).
-- Se aplica solo al crear el volumen: `DEV_SEED=full` (el valor por defecto de compose) lo corre desde
-- db/init/10-roles.sh. No es idempotente: aborta si ya hay datos.
-- =============================================================================

BEGIN;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM libros) OR EXISTS (SELECT 1 FROM socios) THEN
        RAISE EXCEPTION 'La base ya tiene datos; el seed no se aplica dos veces';
    END IF;
END $$;

-- -----------------------------------------------------------------------------
-- Editoriales (16)
-- -----------------------------------------------------------------------------
INSERT INTO editoriales (nombre, pais) VALUES
    ('Sudamericana',   'Argentina'),
    ('Alfaguara',      'España'),
    ('Alianza',        'España'),
    ('Debate',         'España'),
    ('Seix Barral',    'España'),
    ('Editorial del Sol', 'España'),
    ('Siglo XXI',      'México'),
    ('Prentice Hall',  'Estados Unidos'),
    ('Pearson',        'Reino Unido'),
    ('Addison-Wesley', 'Estados Unidos'),
    ('MIT Press',      'Estados Unidos'),
    ('Springer',       'Alemania'),
    ('Wiley',          'Estados Unidos'),
    ('McGraw-Hill',    'Estados Unidos'),
    ('Cengage',        'Estados Unidos'),
    ('O''Reilly',      'Estados Unidos');

-- -----------------------------------------------------------------------------
-- Categorías (15)
-- -----------------------------------------------------------------------------
INSERT INTO categorias (nombre, descripcion) VALUES
    ('Literatura Latinoamericana', 'Novela de autores latinoamericanos'),
    ('Cuento',                     'Colecciones de cuentos y relatos breves'),
    ('Poesía',                     'Poesía y antologías poéticas'),
    ('Ensayo',                     'Ensayo y pensamiento crítico'),
    ('Ciencias de la Computación', 'Fundamentos: algoritmos, sistemas, redes y bases de datos'),
    ('Ingeniería de Software',     'Diseño, calidad y práctica profesional del software'),
    ('Inteligencia Artificial',    'Fundamentos y agentes inteligentes'),
    ('Aprendizaje Automático',     'Machine learning y deep learning'),
    ('Programación',               'Lenguajes y técnicas de programación'),
    ('Matemática',                 'Análisis, álgebra y matemática aplicada'),
    ('Física',                     'Física general y aplicada'),
    ('Historia',                   'Historia universal y regional'),
    ('Educación',                  'Pedagogía y teoría de la educación'),
    ('Filosofía',                  'Filosofía y teoría del conocimiento'),
    ('Divulgación Científica',     'Ciencia para el público general');

-- -----------------------------------------------------------------------------
-- Autores (33)
-- -----------------------------------------------------------------------------
INSERT INTO autores (nombre, apellido, nacionalidad, fecha_nacimiento) VALUES
    ('Gabriel',    'García Márquez', 'Colombia',       '1927-03-06'),
    ('Jorge Luis', 'Borges',         'Argentina',      '1899-08-24'),
    ('Julio',      'Cortázar',       'Argentina',      '1914-08-26'),
    ('Mario',      'Vargas Llosa',   'Perú',           '1936-03-28'),
    ('Ernesto',    'Sabato',         'Argentina',      '1911-06-24'),
    ('Paulo',      'Freire',         'Brasil',         '1921-09-19'),
    ('Yuval Noah', 'Harari',         'Israel',         '1976-02-24'),
    ('James',      'Stewart',        'Canadá',         NULL),
    ('Robert C.',  'Martin',         'Estados Unidos', NULL),
    ('Stuart',     'Russell',        'Reino Unido',    NULL),
    ('Peter',      'Norvig',         'Estados Unidos', NULL),
    ('Thomas H.',  'Cormen',         'Estados Unidos', NULL),
    ('Charles E.', 'Leiserson',      'Estados Unidos', NULL),
    ('Ronald L.',  'Rivest',         'Estados Unidos', NULL),
    ('Clifford',   'Stein',          'Estados Unidos', NULL),
    ('Erich',      'Gamma',          'Suiza',          NULL),
    ('Richard',    'Helm',           'Estados Unidos', NULL),
    ('Ralph',      'Johnson',        'Estados Unidos', NULL),
    ('John',       'Vlissides',      'Estados Unidos', NULL),
    ('Ian',        'Goodfellow',     'Estados Unidos', NULL),
    ('Yoshua',     'Bengio',         'Canadá',         NULL),
    ('Aaron',      'Courville',      'Canadá',         NULL),
    ('Christopher M.', 'Bishop',     'Reino Unido',    NULL),
    ('Abraham',    'Silberschatz',   'Estados Unidos', NULL),
    ('Peter B.',   'Galvin',         'Estados Unidos', NULL),
    ('Greg',       'Gagne',          'Estados Unidos', NULL),
    ('Henry F.',   'Korth',          'Estados Unidos', NULL),
    ('S.',         'Sudarshan',      'India',          NULL),
    ('Andrew S.',  'Tanenbaum',      'Estados Unidos', '1944-03-16'),
    ('David J.',   'Wetherall',      'Reino Unido',    NULL),
    ('Luciano',    'Ramalho',        'Brasil',         NULL),
    ('Andrew',     'Hunt',           'Estados Unidos', NULL),
    ('David',      'Thomas',         'Reino Unido',    NULL);

-- -----------------------------------------------------------------------------
-- Libros (19) — ejemplares_disponibles se recalcula más abajo según los préstamos
-- -----------------------------------------------------------------------------
INSERT INTO libros (titulo, isbn, editorial_id, categoria_id, anio_publicacion, ejemplares_totales, ejemplares_disponibles)
SELECT v.titulo, v.isbn, e.id, c.id, v.anio, v.totales, v.totales
FROM (VALUES
    ('Cien años de soledad',                       '9789500726092', 'Sudamericana',      'Literatura Latinoamericana', 2005, 4),
    ('Rayuela',                                    '9789505111879', 'Alfaguara',         'Literatura Latinoamericana', 1995, 2),
    ('La ciudad y los perros',                     '9788432221026', 'Seix Barral',       'Literatura Latinoamericana', 1984, 2),
    ('Sobre héroes y tumbas',                      '9788495594006', 'Editorial del Sol', 'Literatura Latinoamericana', 2000, 2),
    ('El Aleph',                                   '9789504001935', 'Alianza',           'Cuento',                     2006, 2),
    ('Pedagogía del oprimido',                     '9789682325892', 'Siglo XXI',         'Educación',                  2007, 1),
    ('Sapiens: de animales a dioses',              '9788499926223', 'Debate',            'Historia',                   2015, 3),
    ('Calculus',                                   '9780840058188', 'Cengage',           'Matemática',                 2012, 3),
    ('Clean Code',                                 '9780132350884', 'Prentice Hall',     'Ingeniería de Software',     2008, 4),
    ('Design Patterns',                            '9780201633610', 'Addison-Wesley',    'Ingeniería de Software',     1995, 2),
    ('The Pragmatic Programmer',                   '9780135957059', 'Addison-Wesley',    'Ingeniería de Software',     2019, 2),
    ('Artificial Intelligence: A Modern Approach', '9780134610993', 'Pearson',           'Inteligencia Artificial',    2020, 3),
    ('Deep Learning',                              '9780262035613', 'MIT Press',         'Aprendizaje Automático',     2016, 2),
    ('Pattern Recognition and Machine Learning',   '9780387310732', 'Springer',          'Aprendizaje Automático',     2006, 2),
    ('Introduction to Algorithms',                 '9780262046305', 'MIT Press',         'Ciencias de la Computación', 2022, 3),
    ('Operating System Concepts',                  '9781118063330', 'Wiley',             'Ciencias de la Computación', 2013, 3),
    ('Computer Networks',                          '9780132126953', 'Pearson',           'Ciencias de la Computación', 2011, 3),
    ('Database System Concepts',                   '9780078022159', 'McGraw-Hill',       'Ciencias de la Computación', 2019, 3),
    ('Fluent Python',                              '9781492056355', 'O''Reilly',         'Programación',               2022, 2)
) AS v(titulo, isbn, editorial, categoria, anio, totales)
JOIN editoriales e ON e.nombre = v.editorial
JOIN categorias  c ON c.nombre = v.categoria;

-- -----------------------------------------------------------------------------
-- Libros ↔ autores (N:M)
-- -----------------------------------------------------------------------------
INSERT INTO libros_autores (libro_id, autor_id, orden)
SELECT l.id, a.id, v.orden
FROM (VALUES
    ('9789500726092', 'García Márquez', 1),
    ('9789505111879', 'Cortázar',       1),
    ('9788432221026', 'Vargas Llosa',   1),
    ('9788495594006', 'Sabato',         1),
    ('9789504001935', 'Borges',         1),
    ('9789682325892', 'Freire',         1),
    ('9788499926223', 'Harari',         1),
    ('9780840058188', 'Stewart',        1),
    ('9780132350884', 'Martin',         1),
    ('9780201633610', 'Gamma',          1),
    ('9780201633610', 'Helm',           2),
    ('9780201633610', 'Johnson',        3),
    ('9780201633610', 'Vlissides',      4),
    ('9780135957059', 'Hunt',           1),
    ('9780135957059', 'Thomas',         2),
    ('9780134610993', 'Russell',        1),
    ('9780134610993', 'Norvig',         2),
    ('9780262035613', 'Goodfellow',     1),
    ('9780262035613', 'Bengio',         2),
    ('9780262035613', 'Courville',      3),
    ('9780387310732', 'Bishop',         1),
    ('9780262046305', 'Cormen',         1),
    ('9780262046305', 'Leiserson',      2),
    ('9780262046305', 'Rivest',         3),
    ('9780262046305', 'Stein',          4),
    ('9781118063330', 'Silberschatz',   1),
    ('9781118063330', 'Galvin',         2),
    ('9781118063330', 'Gagne',          3),
    ('9780132126953', 'Tanenbaum',      1),
    ('9780132126953', 'Wetherall',      2),
    ('9780078022159', 'Silberschatz',   1),
    ('9780078022159', 'Korth',          2),
    ('9780078022159', 'Sudarshan',      3),
    ('9781492056355', 'Ramalho',        1)
) AS v(isbn, apellido, orden)
JOIN libros  l ON l.isbn = v.isbn
JOIN autores a ON a.apellido = v.apellido;

-- -----------------------------------------------------------------------------
-- Ampliación del catálogo: cómics (DC, Marvel), fantasía (Empyrean, Tolkien, Narnia, Harry Potter)
-- y manga (Berserk, Dragon Ball): 51 libros más. ISBN, editorial y año verificados en Open Library.
-- Va después de libros_autores base porque su vínculo con autores usa nombre + apellido.
-- Todos los ejemplares nuevos quedan disponibles (sin préstamos).
-- -----------------------------------------------------------------------------
-- Editoriales (12)
INSERT INTO editoriales (nombre, pais) VALUES
    ('Minotauro', 'España'),
    ('Booket', 'España'),
    ('Planeta', 'España'),
    ('Planeta México', 'México'),
    ('Destino', 'España'),
    ('Planetalector', 'España'),
    ('Salamandra', 'España'),
    ('DC Comics', 'Estados Unidos'),
    ('Vertigo', 'Estados Unidos'),
    ('Marvel Comics', 'Estados Unidos'),
    ('Dark Horse', 'Estados Unidos'),
    ('Viz Media', 'Estados Unidos')
ON CONFLICT (nombre) DO NOTHING;

-- Categorías (3)
INSERT INTO categorias (nombre, descripcion) VALUES
    ('Cómics', 'Novela gráfica y cómics de superhéroes'),
    ('Manga', 'Historietas japonesas en formato tankōbon'),
    ('Fantasía', 'Fantasía épica, mundos secundarios y literatura juvenil fantástica')
ON CONFLICT (nombre) DO NOTHING;

-- Autores (24)
INSERT INTO autores (nombre, apellido, nacionalidad, fecha_nacimiento) VALUES
    ('Alan', 'Moore', 'Reino Unido', '1953-11-18'),
    ('Dave', 'Gibbons', 'Reino Unido', '1949-04-14'),
    ('Frank', 'Miller', 'Estados Unidos', '1957-01-27'),
    ('David', 'Mazzucchelli', 'Estados Unidos', '1960-10-21'),
    ('Brian', 'Bolland', 'Reino Unido', '1951-03-26'),
    ('David', 'Lloyd', 'Reino Unido', NULL),
    ('Neil', 'Gaiman', 'Reino Unido', '1960-11-10'),
    ('Mark', 'Millar', 'Reino Unido', '1969-12-24'),
    ('Jeph', 'Loeb', 'Estados Unidos', '1958-09-29'),
    ('Jim', 'Lee', 'Estados Unidos', '1964-08-11'),
    ('Brian', 'Azzarello', 'Estados Unidos', '1962-08-07'),
    ('Mark', 'Waid', 'Estados Unidos', '1962-03-21'),
    ('Alex', 'Ross', 'Estados Unidos', '1970-01-22'),
    ('Jim', 'Starlin', 'Estados Unidos', '1949-10-09'),
    ('Kurt', 'Busiek', 'Estados Unidos', '1960-09-16'),
    ('Brian Michael', 'Bendis', 'Estados Unidos', '1967-08-18'),
    ('Robert', 'Kirkman', 'Estados Unidos', '1978-11-30'),
    ('Steve', 'McNiven', 'Canadá', NULL),
    ('J. R. R.', 'Tolkien', 'Reino Unido', '1892-01-03'),
    ('C. S.', 'Lewis', 'Reino Unido', '1898-11-29'),
    ('J. K.', 'Rowling', 'Reino Unido', '1965-07-31'),
    ('Rebecca', 'Yarros', 'Estados Unidos', NULL),
    ('Kentaro', 'Miura', 'Japón', '1966-07-11'),
    ('Akira', 'Toriyama', 'Japón', '1955-04-05')
ON CONFLICT (nombre, apellido) DO NOTHING;

-- Libros (51)
INSERT INTO libros (titulo, isbn, editorial_id, categoria_id, anio_publicacion, ejemplares_totales, ejemplares_disponibles)
SELECT v.titulo, v.isbn, e.id, c.id, v.anio, v.totales, v.totales
FROM (VALUES
    ('Watchmen', '9781401245252', 'DC Comics', 'Cómics', 2014, 2),
    ('Batman: The Dark Knight Returns', '9781563893421', 'DC Comics', 'Cómics', 1996, 2),
    ('Batman: Year One', '9780930289331', 'DC Comics', 'Cómics', 1988, 2),
    ('Batman: The Killing Joke', '9781401216672', 'DC Comics', 'Cómics', 2008, 2),
    ('V for Vendetta', '9781401207922', 'DC Comics', 'Cómics', 2005, 2),
    ('The Sandman: Preludes & Nocturnes', '9781401225759', 'Vertigo', 'Cómics', 2010, 2),
    ('Superman: Red Son', '9781401247119', 'DC Comics', 'Cómics', 2014, 2),
    ('Batman: Hush', '9781401266134', 'DC Comics', 'Cómics', 2016, 2),
    ('Wonder Woman: Blood', '9781401235628', 'DC Comics', 'Cómics', 2013, 2),
    ('Kingdom Come', '9781563893308', 'DC Comics', 'Cómics', 1997, 2),
    ('Civil War', '9780785121794', 'Marvel Comics', 'Cómics', 2007, 2),
    ('The Infinity Gauntlet', '9780871359445', 'Marvel Comics', 'Cómics', 1992, 2),
    ('Daredevil: Born Again', '9780785134800', 'Marvel Comics', 'Cómics', 2009, 2),
    ('Marvels', '9780785100492', 'Marvel Comics', 'Cómics', 2001, 2),
    ('Ultimate Spider-Man: Power and Responsibility', '9781302918866', 'Marvel Comics', 'Cómics', 2019, 2),
    ('Old Man Logan', '9780785131724', 'Marvel Comics', 'Cómics', 2010, 2),
    ('House of M', '9780785117216', 'Marvel Comics', 'Cómics', 2006, 2),
    ('Avengers Disassembled', '9780785114826', 'Marvel Comics', 'Cómics', 2005, 2),
    ('Marvel Zombies', '9780785122777', 'Marvel Comics', 'Cómics', 2006, 2),
    ('The Thanos Quest', '9780871356826', 'Marvel Comics', 'Cómics', 1990, 2),
    ('Alas de sangre', '9788408279990', 'Planeta', 'Fantasía', 2023, 3),
    ('Alas de hierro', '9788408284550', 'Planeta', 'Fantasía', 2024, 3),
    ('Alas de ónix', '9788408297079', 'Planeta', 'Fantasía', 2025, 3),
    ('El Silmarillion', '9786070710087', 'Planeta México', 'Fantasía', 2022, 3),
    ('El Hobbit', '9788445000656', 'Booket', 'Fantasía', 2012, 3),
    ('El Señor de los Anillos I: La Comunidad del Anillo', '9788445000663', 'Minotauro', 'Fantasía', 2012, 3),
    ('El Señor de los Anillos II: Las Dos Torres', '9788445000670', 'Booket', 'Fantasía', 2012, 3),
    ('El Señor de los Anillos III: El Retorno del Rey', '9788445000687', 'Booket', 'Fantasía', 2012, 3),
    ('Las crónicas de Narnia: El león, la bruja y el armario', '9788408061441', 'Destino', 'Fantasía', 2005, 2),
    ('Las crónicas de Narnia: El príncipe Caspian', '9788467215106', 'Destino', 'Fantasía', 2005, 2),
    ('Las crónicas de Narnia: La travesía del Viajero del Alba', '9788408046028', 'Planetalector', 'Fantasía', 2013, 2),
    ('Las crónicas de Narnia: La silla de plata', '9788408046035', 'Planetalector', 'Fantasía', 2013, 2),
    ('Las crónicas de Narnia: El caballo y el muchacho', '9788408057048', 'Destino', 'Fantasía', 2005, 2),
    ('Las crónicas de Narnia: El sobrino del mago', '9788408057024', 'Destino', 'Fantasía', 2005, 2),
    ('Las crónicas de Narnia: La última batalla', '9788408046233', 'Planetalector', 'Fantasía', 2013, 2),
    ('Harry Potter y la piedra filosofal', '9788478886548', 'Salamandra', 'Fantasía', 2001, 3),
    ('Harry Potter y la cámara secreta', '9788478886562', 'Salamandra', 'Fantasía', 2001, 3),
    ('Harry Potter y el prisionero de Azkaban', '9788478886555', 'Salamandra', 'Fantasía', 2001, 3),
    ('Harry Potter y el cáliz de fuego', '9788498380200', 'Salamandra', 'Fantasía', 2006, 3),
    ('Harry Potter y la Orden del Fénix', '9788478889013', 'Salamandra', 'Fantasía', 2004, 3),
    ('Harry Potter y el misterio del príncipe', '9788498384475', 'Salamandra', 'Fantasía', 2012, 3),
    ('Harry Potter y las reliquias de la muerte', '9788498381467', 'Salamandra', 'Fantasía', 2008, 3),
    ('Berserk Deluxe Edition, Vol. 1', '9781506711980', 'Dark Horse', 'Manga', 2019, 2),
    ('Berserk Deluxe Edition, Vol. 2', '9781506711997', 'Dark Horse', 'Manga', 2019, 2),
    ('Berserk Deluxe Edition, Vol. 3', '9781506712000', 'Dark Horse', 'Manga', 2019, 2),
    ('Berserk Deluxe Edition, Vol. 4', '9781506715216', 'Dark Horse', 'Manga', 2020, 2),
    ('Berserk Deluxe Edition, Vol. 5', '9781506715223', 'Dark Horse', 'Manga', 2020, 2),
    ('Dragon Ball, Vol. 1', '9781569319208', 'Viz Media', 'Manga', 2003, 2),
    ('Dragon Ball, Vol. 2', '9781569319215', 'Viz Media', 'Manga', 2003, 2),
    ('Dragon Ball Z, Vol. 1', '9781421520643', 'Viz Media', 'Manga', 2008, 2),
    ('Dragon Ball Z, Vol. 2 (VIZBIG Edition)', '9781421520650', 'Viz Media', 'Manga', 2008, 2)
) AS v(titulo, isbn, editorial, categoria, anio, totales)
JOIN editoriales e ON e.nombre = v.editorial
JOIN categorias  c ON c.nombre = v.categoria
ON CONFLICT (isbn) DO NOTHING;

-- Libros ↔ autores (N:M)
INSERT INTO libros_autores (libro_id, autor_id, orden)
SELECT l.id, a.id, v.orden
FROM (VALUES
    ('9781401245252', 'Alan', 'Moore', 1),
    ('9781401245252', 'Dave', 'Gibbons', 2),
    ('9781563893421', 'Frank', 'Miller', 1),
    ('9780930289331', 'Frank', 'Miller', 1),
    ('9780930289331', 'David', 'Mazzucchelli', 2),
    ('9781401216672', 'Alan', 'Moore', 1),
    ('9781401216672', 'Brian', 'Bolland', 2),
    ('9781401207922', 'Alan', 'Moore', 1),
    ('9781401207922', 'David', 'Lloyd', 2),
    ('9781401225759', 'Neil', 'Gaiman', 1),
    ('9781401247119', 'Mark', 'Millar', 1),
    ('9781401266134', 'Jeph', 'Loeb', 1),
    ('9781401266134', 'Jim', 'Lee', 2),
    ('9781401235628', 'Brian', 'Azzarello', 1),
    ('9781563893308', 'Mark', 'Waid', 1),
    ('9781563893308', 'Alex', 'Ross', 2),
    ('9780785121794', 'Mark', 'Millar', 1),
    ('9780785121794', 'Steve', 'McNiven', 2),
    ('9780871359445', 'Jim', 'Starlin', 1),
    ('9780785134800', 'Frank', 'Miller', 1),
    ('9780785134800', 'David', 'Mazzucchelli', 2),
    ('9780785100492', 'Kurt', 'Busiek', 1),
    ('9780785100492', 'Alex', 'Ross', 2),
    ('9781302918866', 'Brian Michael', 'Bendis', 1),
    ('9780785131724', 'Mark', 'Millar', 1),
    ('9780785131724', 'Steve', 'McNiven', 2),
    ('9780785117216', 'Brian Michael', 'Bendis', 1),
    ('9780785114826', 'Brian Michael', 'Bendis', 1),
    ('9780785122777', 'Robert', 'Kirkman', 1),
    ('9780871356826', 'Jim', 'Starlin', 1),
    ('9788408279990', 'Rebecca', 'Yarros', 1),
    ('9788408284550', 'Rebecca', 'Yarros', 1),
    ('9788408297079', 'Rebecca', 'Yarros', 1),
    ('9786070710087', 'J. R. R.', 'Tolkien', 1),
    ('9788445000656', 'J. R. R.', 'Tolkien', 1),
    ('9788445000663', 'J. R. R.', 'Tolkien', 1),
    ('9788445000670', 'J. R. R.', 'Tolkien', 1),
    ('9788445000687', 'J. R. R.', 'Tolkien', 1),
    ('9788408061441', 'C. S.', 'Lewis', 1),
    ('9788467215106', 'C. S.', 'Lewis', 1),
    ('9788408046028', 'C. S.', 'Lewis', 1),
    ('9788408046035', 'C. S.', 'Lewis', 1),
    ('9788408057048', 'C. S.', 'Lewis', 1),
    ('9788408057024', 'C. S.', 'Lewis', 1),
    ('9788408046233', 'C. S.', 'Lewis', 1),
    ('9788478886548', 'J. K.', 'Rowling', 1),
    ('9788478886562', 'J. K.', 'Rowling', 1),
    ('9788478886555', 'J. K.', 'Rowling', 1),
    ('9788498380200', 'J. K.', 'Rowling', 1),
    ('9788478889013', 'J. K.', 'Rowling', 1),
    ('9788498384475', 'J. K.', 'Rowling', 1),
    ('9788498381467', 'J. K.', 'Rowling', 1),
    ('9781506711980', 'Kentaro', 'Miura', 1),
    ('9781506711997', 'Kentaro', 'Miura', 1),
    ('9781506712000', 'Kentaro', 'Miura', 1),
    ('9781506715216', 'Kentaro', 'Miura', 1),
    ('9781506715223', 'Kentaro', 'Miura', 1),
    ('9781569319208', 'Akira', 'Toriyama', 1),
    ('9781569319215', 'Akira', 'Toriyama', 1),
    ('9781421520643', 'Akira', 'Toriyama', 1),
    ('9781421520650', 'Akira', 'Toriyama', 1)
) AS v(isbn, nombre, apellido, orden)
JOIN libros  l ON l.isbn = v.isbn
JOIN autores a ON a.nombre = v.nombre AND a.apellido = v.apellido
ON CONFLICT (libro_id, autor_id) DO NOTHING;

-- -----------------------------------------------------------------------------
-- Socios (20, sintéticos): 14 alumnos + 6 docentes
-- -----------------------------------------------------------------------------
INSERT INTO socios (nombre, apellido, legajo, tipo_socio, email, fecha_alta) VALUES
    ('Juan',      'Pérez',     'A-1001', 'alumno',  'juan.perez@alumnos.example.edu.ar',      CURRENT_DATE - 700),
    ('María',     'González',  'A-1002', 'alumno',  'maria.gonzalez@alumnos.example.edu.ar',  CURRENT_DATE - 650),
    ('Lucas',     'Fernández', 'A-1003', 'alumno',  'lucas.fernandez@alumnos.example.edu.ar', CURRENT_DATE - 600),
    ('Sofía',     'Rodríguez', 'A-1004', 'alumno',  'sofia.rodriguez@alumnos.example.edu.ar', CURRENT_DATE - 580),
    ('Martín',    'López',     'A-1005', 'alumno',  'martin.lopez@alumnos.example.edu.ar',    CURRENT_DATE - 540),
    ('Valentina', 'Martínez',  'A-1006', 'alumno',  'valentina.martinez@alumnos.example.edu.ar', CURRENT_DATE - 500),
    ('Nicolás',   'Gómez',     'A-1007', 'alumno',  'nicolas.gomez@alumnos.example.edu.ar',   CURRENT_DATE - 470),
    ('Camila',    'Díaz',      'A-1008', 'alumno',  'camila.diaz@alumnos.example.edu.ar',     CURRENT_DATE - 430),
    ('Tomás',     'Romero',    'A-1009', 'alumno',  'tomas.romero@alumnos.example.edu.ar',    CURRENT_DATE - 400),
    ('Julieta',   'Álvarez',   'A-1010', 'alumno',  'julieta.alvarez@alumnos.example.edu.ar', CURRENT_DATE - 360),
    ('Facundo',   'Torres',    'A-1011', 'alumno',  'facundo.torres@alumnos.example.edu.ar',  CURRENT_DATE - 320),
    ('Agustina',  'Ruiz',      'A-1012', 'alumno',  'agustina.ruiz@alumnos.example.edu.ar',   CURRENT_DATE - 280),
    ('Santiago',  'Sosa',      'A-1013', 'alumno',  'santiago.sosa@alumnos.example.edu.ar',   CURRENT_DATE - 240),
    ('Florencia', 'Benítez',   'A-1014', 'alumno',  'florencia.benitez@alumnos.example.edu.ar', CURRENT_DATE - 200),
    ('Laura',     'Acosta',    'D-2001', 'docente', 'laura.acosta@docentes.example.edu.ar',   CURRENT_DATE - 1500),
    ('Roberto',   'Medina',    'D-2002', 'docente', 'roberto.medina@docentes.example.edu.ar', CURRENT_DATE - 1400),
    ('Patricia',  'Herrera',   'D-2003', 'docente', 'patricia.herrera@docentes.example.edu.ar', CURRENT_DATE - 1200),
    ('Gustavo',   'Silva',     'D-2004', 'docente', 'gustavo.silva@docentes.example.edu.ar',  CURRENT_DATE - 1000),
    ('Marcela',   'Castro',    'D-2005', 'docente', 'marcela.castro@docentes.example.edu.ar', CURRENT_DATE - 900),
    ('Daniel',    'Ortiz',     'D-2006', 'docente', 'daniel.ortiz@docentes.example.edu.ar',   CURRENT_DATE - 800);

-- -----------------------------------------------------------------------------
-- Préstamos (28, sintéticos). Plazos según reglamento: alumno 14 d, docente 30 d.
-- dias_atras = hace cuántos días se retiró; retenido = días hasta devolver (NULL = no devuelto)
--   Devueltos:  1-18  (algunos con atraso)
--   Activos:    19-23 (dentro de plazo)
--   Vencidos:   24-28 (activos fuera de plazo)
-- -----------------------------------------------------------------------------
INSERT INTO prestamos (libro_id, socio_id, fecha_prestamo, fecha_devolucion_prevista, fecha_devolucion_real, estado)
SELECT l.id, s.id,
       CURRENT_DATE - v.dias_atras,
       CURRENT_DATE - v.dias_atras + v.plazo,
       CASE WHEN v.retenido IS NULL THEN NULL ELSE CURRENT_DATE - v.dias_atras + v.retenido END,
       CASE WHEN v.retenido IS NULL THEN 'activo' ELSE 'devuelto' END
FROM (VALUES
    -- legajo,  isbn,            dias_atras, plazo, retenido
    ('A-1002', '9780132350884',  90, 14, 12),
    ('A-1003', '9780132350884',  75, 14, 20),
    ('A-1005', '9780132350884',  60, 14, 10),
    ('A-1008', '9780134610993',  80, 14, 14),
    ('D-2001', '9780134610993',  70, 30, 25),
    ('A-1004', '9789500726092',  85, 14,  9),
    ('A-1006', '9789500726092',  50, 14, 18),
    ('A-1007', '9780262046305',  65, 14, 13),
    ('A-1009', '9780078022159',  55, 14, 14),
    ('D-2002', '9780262035613',  45, 30, 30),
    ('A-1010', '9789505111879',  40, 14,  7),
    ('A-1011', '9788499926223',  35, 14, 15),
    ('A-1013', '9781492056355',  30, 14, 11),
    ('D-2003', '9780135957059',  28, 30, 20),
    ('A-1012', '9789504001935',  25, 14,  8),
    ('A-1002', '9780201633610', 100, 14, 14),
    ('A-1001', '9780132350884', 110, 14, 13),
    ('D-2004', '9781118063330',  60, 30, 33),
    -- activos dentro de plazo
    ('A-1014', '9780132350884',   5, 14, NULL),
    ('A-1005', '9780132126953',   3, 14, NULL),
    ('D-2005', '9780387310732',  10, 30, NULL),
    ('A-1003', '9789500726092',   8, 14, NULL),
    ('D-2006', '9780840058188',  12, 30, NULL),
    -- vencidos
    ('A-1001', '9788495594006',  20, 14, NULL),
    ('A-1009', '9780134610993',  25, 14, NULL),
    ('A-1011', '9780132350884',  18, 14, NULL),
    ('D-2002', '9789682325892',  45, 30, NULL),
    ('A-1007', '9788432221026',  16, 14, NULL)
) AS v(legajo, isbn, dias_atras, plazo, retenido)
JOIN socios s ON s.legajo = v.legajo
JOIN libros l ON l.isbn   = v.isbn;

-- Disponibilidad coherente con los préstamos aún no devueltos
UPDATE libros l
SET ejemplares_disponibles = l.ejemplares_totales - COALESCE(
    (SELECT COUNT(*) FROM prestamos p WHERE p.libro_id = l.id AND p.estado = 'activo'), 0);

COMMIT;
