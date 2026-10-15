-- =============================================================================
-- Pipidu Library Agent — Ampliación del catálogo (cómics, fantasía y manga)
-- Agrega 51 libros al seed base (db/seed.sql). ISBN, editorial y año verificados en Open Library.
-- Es ADITIVO e IDEMPOTENTE: ON CONFLICT DO NOTHING en todas las tablas (se puede aplicar más de una vez)
-- y no toca socios ni préstamos. Aplicar DESPUÉS de db/schema.sql y db/seed.sql.
--   psql "$DATABASE_URL_UNPOOLED" -v ON_ERROR_STOP=1 -f db/seed_ampliacion.sql
-- Los ejemplares nuevos quedan todos disponibles (sin préstamos): ejemplares_disponibles = totales.
-- =============================================================================

BEGIN;

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

COMMIT;
