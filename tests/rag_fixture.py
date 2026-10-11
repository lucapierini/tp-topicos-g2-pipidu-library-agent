"""Corpus simulado y recuperador léxico para medir el agente sin PDFs ni ingesta (T3.x pendiente, D19).

Qué es: un `RagRetriever` **real** (top-k, umbral y reporte de no-relevancia de `agent/tools/rag_tool.py`)
sobre un `InMemoryVectorStore` con un puñado de fragmentos escritos a mano y un embedder léxico
(bolsa de palabras, determinista, sin red).

Qué NO es: no mide la calidad de la recuperación semántica. Las similitudes de un embedder léxico no son
comparables con las de `gemini-embedding-001`, así que el umbral de acá (`MOCK_SIMILARITY_THRESHOLD`) no
tiene relación con D12 y no calibra nada (R-4.8). El contenido de los documentos es de prueba: no es el
reglamento real. Toda medición hecha con este corpus debe declararlo (R-2.8, `AGENTS.md` §4).
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import replace

from agent.config import Config
from agent.contracts import Chunk
from agent.tools.rag_tool import InMemoryVectorStore, RagRetriever

# Umbral propio del embedder léxico: separa "tiene palabras en común" de "no tiene ninguna relevante".
MOCK_SIMILARITY_THRESHOLD = 0.15

# (documento, ubicación, texto). Las ubicaciones imitan lo que la ingesta debe guardar en `metadata`.
CORPUS: list[tuple[str, str, str]] = [
    ("reglamento_biblioteca.pdf", "Art. 12",
     "El plazo de devolución de un libro prestado es de 15 días corridos para los alumnos. Vencido el "
     "plazo, corresponde una multa de un día de suspensión por cada día de atraso."),
    ("reglamento_biblioteca.pdf", "Art. 13",
     "Los docentes disponen de un plazo de devolución de 30 días corridos para los libros prestados. La "
     "multa por atraso es la misma que para los alumnos."),
    ("reglamento_biblioteca.pdf", "Art. 14",
     "Cada socio puede renovar un préstamo hasta 2 veces, siempre que el libro no tenga reservas y el "
     "préstamo no esté vencido."),
    ("reglamento_biblioteca.pdf", "Art. 20",
     "El horario de atención de la biblioteca es de lunes a viernes de 8 a 20 horas y los sábados de 9 a "
     "13 horas. Los domingos y feriados permanece cerrada."),
    ("manual_uso_sistema.pdf", "Sección 3.2",
     "Pasos para renovar un préstamo desde el sistema: ingresá con tu usuario, abrí Mis préstamos, "
     "elegí el libro y presioná Renovar."),
    ("manual_uso_sistema.pdf", "Sección 2.1",
     "Para buscar un libro en el catálogo ingresá el título, el autor o la categoría en el buscador."),
    ("resenas_libro_1.pdf", "Reseña",
     "Cien años de soledad es una novela de Gabriel García Márquez que narra la historia de la familia "
     "Buendía a lo largo de siete generaciones en el pueblo ficticio de Macondo."),
]

_STOPWORDS = frozenset(
    "el la los las un una unos unas de del al en y o a que para por con se es su sus lo como mi me te "
    "tengo tiene tienen cual cuales cuanto cuantos qué cuál si le puede segun hay son esta este libro "
    "libros ser son sobre entre desde hasta".split()
)

# Prefijo -> raíz canónica. Une formas de una misma palabra (renuevo/renovar, devolver/devolución).
_STEMS: tuple[tuple[str, str], ...] = (
    ("renov", "renov"), ("renue", "renov"),
    ("devol", "devol"), ("devuel", "devol"),
    ("prest", "prest"),
    ("mult", "multa"), ("sancion", "multa"),
    ("horario", "horario"), ("atencion", "horario"), ("atiende", "horario"),
    ("sinopsis", "sinopsis"), ("resena", "sinopsis"), ("trata", "sinopsis"), ("narra", "sinopsis"),
    ("plazo", "plazo"),
    # Alias en inglés: un embedding multilingüe (gemini-embedding-001) acerca "return a book" a
    # "devolver un libro"; el embedder léxico necesita decirlo explícitamente (R-5.1).
    ("return", "devol"), ("fine", "multa"), ("penalt", "multa"), ("loan", "prest"), ("renew", "renov"),
    ("deadline", "plazo"), ("schedule", "horario"), ("hour", "horario"), ("synopsis", "sinopsis"),
    ("day", "dia"), ("librar", "biblioteca"),
)


def _tokens(text: str) -> list[str]:
    plain = unicodedata.normalize("NFKD", text.lower()).encode("ascii", "ignore").decode()
    out: list[str] = []
    for word in re.findall(r"[a-z0-9]+", plain):
        if len(word) < 3 or word in _STOPWORDS:
            continue
        for prefix, root in _STEMS:
            if word.startswith(prefix):
                word = root
                break
        else:
            if word.endswith("s") and len(word) > 3:
                word = word[:-1]
        out.append(word)
    return out


class LexicalEmbedder:
    """Bolsa de palabras sobre el vocabulario del corpus: determinista y sin red."""

    def __init__(self, corpus: list[tuple[str, str, str]] = CORPUS) -> None:
        vocabulary = sorted({t for _, _, text in corpus for t in _tokens(text)})
        self._index = {term: i for i, term in enumerate(vocabulary)}

    def embed_query(self, text: str) -> list[float]:
        vector = [0.0] * len(self._index)
        for token in _tokens(text):
            if token in self._index:
                vector[self._index[token]] += 1.0
        return vector


def build_mock_retriever(config: Config) -> RagRetriever:
    """`RagRetriever` real (política de top-k y umbral) sobre el corpus simulado."""
    embedder = LexicalEmbedder()
    items = []
    for i, (document, location, text) in enumerate(CORPUS, start=1):
        digest = hashlib.sha256(f"{document}:{location}".encode()).hexdigest()[:16]
        chunk = Chunk(id=i, document=document, location=location, text=text,
                      content_hash=f"mock:{digest}", similarity=0.0)
        items.append((chunk, embedder.embed_query(f"{location} {text}")))
    mock_config = replace(config, similarity_threshold=MOCK_SIMILARITY_THRESHOLD)
    return RagRetriever(embedder, InMemoryVectorStore(items), mock_config)
