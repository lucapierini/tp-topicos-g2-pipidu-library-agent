"""Set de validación del RAG: consultas NUEVAS para confirmar fuera de muestra (R-4.10, D99).

`tests/calibration_set.py` sirvió para elegir los parámetros de cada estrategia (α del híbrido, el rango de
normalización y los umbrales), así que sus números son optimistas. Este set no se usa para elegir nada: se
aplican los parámetros ya congelados y se mide cuánto se sostiene la mejora.

Se redactó distinto a propósito, como escribe un socio real y no como un autor de tests: coloquial, con contexto
personal, preguntas de varias partes y paráfrasis que no repiten las palabras del documento. Las etiquetas se verifican
igual que las de calibración (`tests/test_validation_set.py`): cada positivo lleva un término que su documento contiene y
cada negativo uno que ningún documento contiene.
"""
from __future__ import annotations

from tests.calibration_set import CalibrationCase

_REG, _POL = "reglamento_biblioteca", "politicas_universidad"
_CIEN, _CLEAN = "resenas_cien_anios_de_soledad", "resenas_clean_code"
_TOLK, _EMP = "resenas_tolkien", "resenas_empyrean"


def _p(n: int, group: str, document: str, question: str, term: str) -> CalibrationCase:
    return CalibrationCase(f"VP{n:02d}", question, True, group, term, document)


def _n(n: int, group: str, question: str, term: str) -> CalibrationCase:
    return CalibrationCase(f"VN{n:02d}", question, False, group, term)


POSITIVES: list[CalibrationCase] = [
    # --- reglamento
    _p(1, "reglamento", _REG, "Soy docente, ¿por cuántos días me puedo llevar un libro?", "30 días corridos"),
    _p(2, "reglamento", _REG, "Me pasé 3 días con un libro, ¿cuánta plata tengo que pagar?", "$200"),
    _p(3, "reglamento", _REG, "¿Hasta qué hora puedo ir a la biblioteca un viernes?", "21:00"),
    _p(4, "reglamento", _REG, "Quiero extender el préstamo de mi libro, ¿se puede y por cuántos días?", "una sola vez"),
    _p(5, "reglamento", _REG, "¿Qué hago si el libro que busco está todo prestado?", "reservarlo"),
    _p(6, "reglamento", _REG, "Reservé un libro y ya lo devolvieron, ¿hasta cuándo me lo guardan?", "48 horas"),
    _p(7, "reglamento", _REG, "Rompí un libro sin querer, ¿qué me piden?", "pérdida o daño"),
    _p(8, "reglamento", _REG, "¿Puedo llevarme a casa un libro marcado como consulta en sala?", "consulta en sala"),
    _p(9, "reglamento", _REG, "¿Cuál es el máximo de libros que puede retirar un profesor?", "5 libros"),
    _p(10, "reglamento", _REG, "¿Se renuevan los libros que ya están vencidos?", "no esté vencido"),
    _p(11, "reglamento", _REG, "¿La biblioteca abre un domingo?", "Domingos y feriados"),
    # --- políticas
    _p(12, "politicas", _POL, "¿Puedo escribir notas en los márgenes de un libro de la biblioteca?", "escribir"),
    _p(13, "politicas", _POL, "¿Me pueden suspender el préstamo por devolver tarde muchas veces?",
       "Suspensión del servicio de préstamo"),
    _p(14, "politicas", _POL, "¿Qué es un apercibimiento?", "Apercibimiento"),
    _p(15, "politicas", _POL, "¿Quién puede ver los datos de mis préstamos?", "terceros ajenos"),
    _p(16, "politicas", _POL, "¿Cómo pido que la biblioteca compre un título?", "formulario del portal"),
    _p(17, "politicas", _POL, "¿Está permitido hablar por teléfono en la sala de lectura?", "mantener silencio"),
    _p(18, "politicas", _POL, "Si dejo de ser alumno regular, ¿puedo seguir sacando libros?", "regularidad"),
    # --- reseñas
    _p(19, "resena_cien_anios", _CIEN, "Contame de qué va Cien años de soledad", "Buendía"),
    _p(20, "resena_cien_anios", _CIEN, "¿Cuántas generaciones abarca la novela de Macondo?", "siete generaciones"),
    _p(21, "resena_clean_code", _CLEAN, "¿Vale la pena leer Clean Code si recién empiezo a programar?", "Estudiantes avanzados"),
    _p(22, "resena_clean_code", _CLEAN, "¿Qué dice la reseña de Clean Code sobre las pruebas unitarias?", "Pruebas unitarias"),
    _p(23, "resena_tolkien", _TOLK, "¿Quién es Bilbo Bolsón?", "Bilbo Bolsón"),
    _p(24, "resena_tolkien", _TOLK, "¿Qué es el Anillo Único?", "Anillo Único"),
    _p(25, "resena_tolkien", _TOLK, "¿En qué año se publicó El Silmarillion?", "1977"),
    _p(26, "resena_tolkien", _TOLK, "¿Qué pasa en la batalla de los Campos del Pelennor?", "Pelennor"),
    _p(27, "resena_empyrean", _EMP, "¿Cómo se llama la academia de dragones de Alas de sangre?", "Basgiath"),
    _p(28, "resena_empyrean", _EMP, "¿Qué cuenta Alas de ónix? ¿Salen de Navarre?", "regiones desconocidas"),
    _p(29, "resena_empyrean", _EMP, "¿La saga Empyrean tiene alguna advertencia de contenido?", "Aviso de contenido"),
    # --- inglés
    _p(30, "en", _REG, "How long can a teacher borrow a book for?", "30 días corridos"),
    _p(31, "en", _REG, "Is there a fine if I return a book late?", "$200"),
    _p(32, "en", _REG, "What time does the library close on weekdays?", "21:00"),
    _p(33, "en", _EMP, "Who is Violet Sorrengail?", "Violet Sorrengail"),
    _p(34, "en", _TOLK, "What is the Silmarillion about?", "Silmarils"),
    _p(35, "en", _POL, "Can I write notes in a library book?", "escribir"),
]

NEGATIVES: list[CalibrationCase] = [
    # --- del dominio, comparten vocabulario con los documentos
    _n(1, "dominio_dificil", "¿Hay enchufes para cargar el celular en la sala de lectura?", "enchufe"),
    _n(2, "dominio_dificil", "¿Cuánto es la multa si me llevo un libro sin registrarlo?", "sin registr"),
    _n(3, "dominio_dificil", "¿La biblioteca tiene aire acondicionado?", "aire acondicionado"),
    _n(4, "dominio_dificil", "¿Puedo llevar mi propia laptop a la sala de lectura?", "laptop"),
    _n(5, "dominio_dificil", "¿Cada cuánto cambian los libros de la sección novedades?", "novedades"),
    _n(6, "dominio_dificil", "¿Hay bibliotecarios que ayuden a buscar bibliografía para mi tesis?", "tesis"),
    _n(7, "dominio_dificil", "¿Se puede pedir un libro prestado por WhatsApp?", "whatsapp"),
    _n(8, "dominio_dificil", "¿Me prestan auriculares en la biblioteca?", "auricular"),
    _n(9, "dominio_dificil", "¿Tienen revistas científicas suscriptas?", "suscri"),
    _n(10, "dominio_dificil", "¿Cuánto tarda en llegar un libro que pedí a otra sede?", "sede"),
    _n(11, "dominio_dificil", "¿Hay un buzón para devolver libros fuera de horario?", "buzón"),
    _n(12, "dominio_dificil", "¿La biblioteca organiza ferias del libro o actividades culturales?", "cultural"),
    _n(13, "dominio_dificil", "¿Puedo rendir un examen en la sala de lectura?", "examen"),
    _n(14, "dominio_dificil", "¿Me dan una constancia de que no adeudo libros?", "constancia"),
    _n(15, "dominio_dificil", "¿Puedo fumar en el patio de la biblioteca?", "fumar"),
    _n(16, "dominio_dificil", "¿Los docentes pagan la mitad de multa por atraso?", "mitad"),
    # --- libros del catálogo sin reseña
    _n(17, "libro_sin_resena", "¿De qué se trata Harry Potter y el prisionero de Azkaban?", "Azkaban"),
    _n(18, "libro_sin_resena", "¿Quién es Batman en The Dark Knight Returns?", "Batman"),
    _n(19, "libro_sin_resena", "¿De qué trata Introduction to Algorithms?", "Algorithms"),
    _n(20, "libro_sin_resena", "¿Cuál es la trama de Sandman?", "Sandman"),
    _n(21, "libro_sin_resena", "¿Qué cuenta El león, la bruja y el ropero?", "ropero"),
    # --- ajenas
    _n(22, "ajeno", "¿Cómo está el dólar hoy?", "dólar"),
    _n(23, "ajeno", "¿Cuál es la receta de las empanadas tucumanas?", "empanada"),
    _n(24, "ajeno", "¿A qué hora juega la selección?", "selección"),
    _n(25, "ajeno", "Ayudame a escribir un mail a mi profesor", "mail"),
    # --- inglés
    _n(26, "en_negativo", "Can I print my thesis at the library?", "tesis"),
    _n(27, "en_negativo", "Do you have a wifi password for guests?", "wifi"),
    _n(28, "en_negativo", "What is Dragon Ball Z about?", "Dragon Ball"),
]

VALIDATION_SET: list[CalibrationCase] = [*POSITIVES, *NEGATIVES]
