"""Set de calibración del umbral de similitud del RAG (R-4.8, D12, D97).

Un umbral elegido con 16 preguntas depende de 2 o 3 casos extremos. Este set tiene ~100 consultas, etiquetadas
con lo que **debe** pasar, para medir el umbral con curvas (recall, falsos positivos, F1) y no con el mejor y el
peor caso.

Cada `CalibrationCase` es verificable **sin red ni base**:

- `covered=True`: los documentos contestan la pregunta. `document` es el prefijo del PDF que debe aparecer arriba
  y `term` un texto que ese documento contiene (si el documento cambia y el término desaparece, la pregunta deja
  de estar cubierta y `tests/test_calibration_set.py` lo avisa).
- `covered=False`: ningún documento la contesta. `term` es una palabra clave que NO aparece en ninguno
  (si un documento nuevo la incorpora, la pregunta deja de ser un negativo y el test lo avisa).

Grupos:

- positivos: `reglamento`, `politicas`, `resena_cien_anios`, `resena_clean_code`, `resena_tolkien`,
  `resena_empyrean` y `en` (preguntas en inglés, que puntúan más bajo contra documentos en castellano).
- negativos: `dominio_dificil` (parecen del dominio y comparten vocabulario con los documentos: los que más
  confunden al umbral), `libro_sin_resena` (libros que están en el catálogo pero no tienen reseña), `ajeno`
  (nada que ver con la biblioteca) y `en_negativo`.

Se usa con `scripts/calibrate_threshold.py`. Los casos del golden set (`R1`–`R16`) se suman ahí sin duplicarse.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CalibrationCase:
    id: str
    question: str
    covered: bool
    group: str
    term: str                    # positivo: aparece en `document`; negativo: no aparece en ningún documento
    document: str | None = None  # prefijo del PDF que debe contestar (solo positivos)


def _p(n: int, group: str, document: str, question: str, term: str) -> CalibrationCase:
    return CalibrationCase(f"CP{n:02d}", question, True, group, term, document)


def _n(n: int, group: str, question: str, term: str) -> CalibrationCase:
    return CalibrationCase(f"CN{n:02d}", question, False, group, term)


_REG, _POL = "reglamento_biblioteca", "politicas_universidad"
_CIEN, _CLEAN = "resenas_cien_anios_de_soledad", "resenas_clean_code"
_TOLK, _EMP = "resenas_tolkien", "resenas_empyrean"

POSITIVES: list[CalibrationCase] = [
    # --- reglamento
    _p(1, "reglamento", _REG, "¿Cuántos días puedo tener un libro prestado siendo alumno?", "14 días corridos"),
    _p(2, "reglamento", _REG, "¿Cuánto tiempo de préstamo tienen los docentes?", "30 días corridos"),
    _p(3, "reglamento", _REG, "¿Cuántos libros puede llevarse un alumno al mismo tiempo?", "3 libros"),
    _p(4, "reglamento", _REG, "¿Y cuántos puede tener un docente a la vez?", "5 libros"),
    _p(5, "reglamento", _REG, "¿Puedo renovar un préstamo más de una vez?", "una sola vez"),
    _p(6, "reglamento", _REG, "¿Cuántos días extiende la renovación si soy docente?", "extiende el plazo"),
    _p(7, "reglamento", _REG, "Si me atraso con un libro, ¿cuánto pago por día?", "$200"),
    _p(8, "reglamento", _REG, "¿Hasta qué hora está abierta la biblioteca los días de semana?", "21:00"),
    _p(9, "reglamento", _REG, "¿La biblioteca abre los sábados?", "Sábados"),
    _p(10, "reglamento", _REG, "¿Atienden los domingos y feriados?", "Domingos y feriados"),
    _p(11, "reglamento", _REG, "¿Qué pasa si pierdo un libro de la biblioteca?", "pérdida o daño"),
    _p(12, "reglamento", _REG, "¿Se pueden sacar los libros de consulta en sala?", "consulta en sala"),
    _p(13, "reglamento", _REG, "¿Puedo reservar un libro que no tiene ejemplares disponibles?", "reservarlo"),
    _p(14, "reglamento", _REG, "¿Cuánto tiempo me guardan el libro que reservé?", "48 horas"),
    _p(15, "reglamento", _REG, "¿Qué necesito para retirar libros por primera vez?", "dado de alta como socio"),
    _p(16, "reglamento", _REG, "¿Puedo retirar libros si tengo uno vencido?", "material vencido"),
    _p(17, "reglamento", _REG, "¿Desde cuándo se cuentan los días de atraso?", "día siguiente"),
    _p(18, "reglamento", _REG, "¿Dónde se paga una multa?", "mostrador"),
    # --- políticas
    _p(19, "politicas", _POL, "¿Puedo subrayar un libro de la biblioteca?", "subrayar"),
    _p(20, "politicas", _POL, "¿Puedo prestarle a un amigo el libro que retiré con mi legajo?", "prestar a terceros"),
    _p(21, "politicas", _POL, "¿Se puede comer en la sala de lectura?", "alimentos"),
    _p(22, "politicas", _POL, "¿Qué sanción hay si me atraso más de 30 días varias veces?", "reincidencia"),
    _p(23, "politicas", _POL, "¿Qué pasa con mis préstamos si pierdo la regularidad como alumno?", "regularidad"),
    _p(24, "politicas", _POL, "¿Qué hace la biblioteca con mis datos personales?", "Datos personales"),
    _p(25, "politicas", _POL, "¿Cómo sugiero que compren un libro nuevo?", "formulario del portal"),
    _p(26, "politicas", _POL, "¿Cada cuánto evalúan las sugerencias de compra?", "una vez por cuatrimestre"),
    _p(27, "politicas", _POL, "¿Puedo usar el celular en la sala de lectura?", "dispositivos móviles"),
    _p(28, "politicas", _POL, "¿Se pueden fotocopiar libros de la biblioteca?", "propiedad intelectual"),
    # --- cien años de soledad
    _p(29, "resena_cien_anios", _CIEN, "¿De qué trata Cien años de soledad?", "Buendía"),
    _p(30, "resena_cien_anios", _CIEN, "¿Quién escribió Cien años de soledad?", "García Márquez"),
    _p(31, "resena_cien_anios", _CIEN, "¿Cuáles son los temas principales de Cien años de soledad?", "tiempo cíclico"),
    _p(32, "resena_cien_anios", _CIEN, "¿Qué es el realismo mágico en la novela de Macondo?", "Realismo mágico"),
    _p(33, "resena_cien_anios", _CIEN, "¿Es difícil seguir la trama de Cien años de soledad?", "nombres repetidos"),
    _p(34, "resena_cien_anios", _CIEN, "¿Para qué lectores se recomienda Cien años de soledad?", "Lectores de narrativa"),
    # --- clean code
    _p(35, "resena_clean_code", _CLEAN, "¿De qué trata Clean Code?", "código limpio"),
    _p(36, "resena_clean_code", _CLEAN, "¿Quién es el autor de Clean Code?", "Robert C. Martin"),
    _p(37, "resena_clean_code", _CLEAN, "¿Qué dice Clean Code sobre los comentarios?", "Comentarios"),
    _p(38, "resena_clean_code", _CLEAN, "¿En qué lenguaje están los ejemplos de Clean Code?", "Java"),
    _p(39, "resena_clean_code", _CLEAN, "¿Qué son los code smells?", "code smells"),
    _p(40, "resena_clean_code", _CLEAN, "¿Quién debería leer Clean Code?", "Estudiantes avanzados"),
    # --- tolkien
    _p(41, "resena_tolkien", _TOLK, "¿De qué trata El Silmarillion?", "Silmarils"),
    _p(42, "resena_tolkien", _TOLK, "¿Es difícil leer El Silmarillion?", "más difícil"),
    _p(43, "resena_tolkien", _TOLK, "¿Quién es Gollum en El Hobbit?", "Gollum"),
    _p(44, "resena_tolkien", _TOLK, "¿Para qué tipo de lector está pensado El Hobbit?", "lectores jóvenes"),
    _p(45, "resena_tolkien", _TOLK, "¿Qué pasa en Las Dos Torres?", "Abismo de Helm"),
    _p(46, "resena_tolkien", _TOLK, "¿Qué es la Comunidad del Anillo?", "nueve compañeros"),
    _p(47, "resena_tolkien", _TOLK, "¿Cómo termina El Retorno del Rey?", "Monte del Destino"),
    _p(48, "resena_tolkien", _TOLK, "¿Por dónde empiezo a leer a Tolkien?", "puerta de entrada"),
    # --- empyrean
    _p(49, "resena_empyrean", _EMP, "¿De qué trata Alas de sangre?", "Cuadrante de Jinetes"),
    _p(50, "resena_empyrean", _EMP, "¿Cuál es el título original de Alas de ónix?", "Onyx Storm"),
    _p(51, "resena_empyrean", _EMP, "¿La saga Empyrean es para adolescentes?", "adultos"),
    _p(52, "resena_empyrean", _EMP, "¿Cómo es el ritmo de Alas de hierro?", "irregular"),
    _p(53, "resena_empyrean", _EMP, "¿Quién es Xaden Riorson?", "Xaden Riorson"),
    _p(54, "resena_empyrean", _EMP, "¿Dónde transcurre la saga Empyrean?", "Navarre"),
    # --- inglés (documentos en castellano)
    _p(55, "en", _REG, "How many days can a student keep a borrowed book?", "14 días corridos"),
    _p(56, "en", _REG, "What is the late fee per day?", "$200"),
    _p(57, "en", _REG, "What are the library opening hours on Saturdays?", "Sábados"),
    _p(58, "en", _REG, "Can I renew a loan more than once?", "una sola vez"),
    _p(59, "en", _TOLK, "What is The Hobbit about?", "Bilbo"),
    _p(60, "en", _CIEN, "Who wrote One Hundred Years of Solitude?", "García Márquez"),
    _p(61, "en", _EMP, "Is Fourth Wing suitable for teenagers?", "adultos"),
    _p(62, "en", _CLEAN, "What does Clean Code say about small functions?", "Funciones pequeñas"),
]

NEGATIVES: list[CalibrationCase] = [
    # --- del dominio, comparten vocabulario con los documentos (los difíciles)
    _n(1, "dominio_dificil", "¿Me puedo conectar al wifi de la biblioteca con mi legajo?", "wifi"),
    _n(2, "dominio_dificil", "¿La biblioteca tiene cafetería?", "cafetería"),
    _n(3, "dominio_dificil", "¿Hay estacionamiento para bicicletas en la biblioteca?", "estacionamiento"),
    _n(4, "dominio_dificil", "¿Cómo reservo una sala de estudio para mi grupo?", "sala de estudio"),
    _n(5, "dominio_dificil", "¿Cuánto cuesta imprimir en la biblioteca?", "imprimir"),
    _n(6, "dominio_dificil", "¿La biblioteca presta notebooks?", "notebook"),
    _n(7, "dominio_dificil", "¿Hay préstamo interbibliotecario con otras universidades?", "interbibliotecario"),
    _n(8, "dominio_dificil", "¿Puedo leer libros electrónicos desde mi casa?", "electrónico"),
    _n(9, "dominio_dificil", "¿Tienen casilleros para guardar las mochilas?", "casillero"),
    _n(10, "dominio_dificil", "¿La biblioteca da talleres de búsqueda bibliográfica?", "taller"),
    _n(11, "dominio_dificil", "¿Cuánto cuesta la cuota para hacerse socio?", "cuota"),
    _n(12, "dominio_dificil", "¿Puedo donar libros a la biblioteca?", "donar"),
    _n(13, "dominio_dificil", "¿Hay servicio de escaneo de documentos?", "escaneo"),
    _n(14, "dominio_dificil", "¿Me pueden enviar un libro a mi domicilio?", "domicilio"),
    _n(15, "dominio_dificil", "¿La biblioteca tiene sala de computadoras?", "computadora"),
    _n(16, "dominio_dificil", "¿Hay descuentos en las multas para docentes?", "descuento"),
    _n(17, "dominio_dificil", "¿Se pueden pagar las multas con tarjeta?", "tarjeta"),
    _n(18, "dominio_dificil", "¿Quién es la directora de la biblioteca?", "directora"),
    _n(19, "dominio_dificil", "¿Cuál es el teléfono de la biblioteca?", "teléfono"),
    _n(20, "dominio_dificil", "¿Tienen una sección infantil?", "infantil"),
    # --- libros del catálogo que NO tienen reseña
    _n(21, "libro_sin_resena", "¿De qué trata Harry Potter y la piedra filosofal?", "Harry Potter"),
    _n(22, "libro_sin_resena", "¿De qué trata Dragon Ball?", "Dragon Ball"),
    _n(23, "libro_sin_resena", "¿Quién es Goku?", "Goku"),
    _n(24, "libro_sin_resena", "¿De qué trata Berserk?", "Berserk"),
    _n(25, "libro_sin_resena", "¿Qué pasa en Las crónicas de Narnia?", "Narnia"),
    _n(26, "libro_sin_resena", "¿Cuál es la trama de Watchmen?", "Watchmen"),
    _n(27, "libro_sin_resena", "¿De qué trata Civil War de Marvel?", "Civil War"),
    _n(28, "libro_sin_resena", "¿De qué trata Fluent Python?", "Fluent Python"),
    _n(29, "libro_sin_resena", "¿Qué explica Deep Learning sobre las redes neuronales?", "redes neuronales"),
    _n(30, "libro_sin_resena", "¿De qué trata Rayuela?", "Rayuela"),
    # --- ajenas a la biblioteca
    _n(31, "ajeno", "¿Qué tiempo hace hoy en Tucumán?", "Tucumán"),
    _n(32, "ajeno", "¿Cómo se hace una tortilla de papas?", "tortilla"),
    _n(33, "ajeno", "¿Quién ganó el último mundial de fútbol?", "fútbol"),
    _n(34, "ajeno", "¿Cuál es la capital de Australia?", "Australia"),
    _n(35, "ajeno", "¿Cómo me inscribo a una materia de la facultad?", "inscrib"),
    _n(36, "ajeno", "¿Cuánto cuesta la cuota de la universidad?", "cuota"),
    _n(37, "ajeno", "Recomendame una película para esta noche", "película"),
    _n(38, "ajeno", "Escribime un poema sobre el mar", "poema"),
    # --- inglés
    _n(39, "en_negativo", "Is there wifi in the reading room?", "wifi"),
    _n(40, "en_negativo", "Can I book a group study room?", "sala de estudio"),
    _n(41, "en_negativo", "What is the weather like today?", "clima"),
    _n(42, "en_negativo", "Does the library have a cafeteria?", "cafetería"),
    _n(43, "en_negativo", "What is Harry Potter about?", "Harry Potter"),
]

CALIBRATION_SET: list[CalibrationCase] = [*POSITIVES, *NEGATIVES]
