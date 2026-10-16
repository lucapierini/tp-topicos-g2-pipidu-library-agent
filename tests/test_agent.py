"""Orquestador (T6.2, T6.3; R-2.x, R-5.x, D1, D3, D8).

Corre sin base, sin API y sin `smolagents`: clasificador, runner, SQL (el executor real sobre una
conexión falsa, validador incluido) y recuperación son dobles de `tests/fakes.py`.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from agent.agent import EmptyQuestionError, LibraryAgent
from agent.classifier import ClassificationError
from agent.config import load_config
from agent.contracts import RagResult
from agent.errors import NO_RELEVANT_RESULTS, RETRIEVAL_ERROR
from tests.fakes import (
    FakeClassifier,
    FakeRetriever,
    ScriptedRunner,
    make_chunk,
    sql_backend,
)

GOOD_SQL = "SELECT l.titulo FROM prestamos p JOIN libros l ON l.id = p.libro_id"
BAD_SQL = "DELETE FROM prestamos"


def _has_source_line(text: str) -> bool:
    """¿El texto trae una línea "Fuente: …" / "Source: …"? La fuente va en `sources` (R-5.2, D84)."""
    return bool(re.search(r"(?mi)^[ \t]*(?:Fuentes?|Sources?)[ \t]*:", text))


def build(label="sql", *, steps=(), text="Tiene 2 libros.", language="es", rows=None, columns=None,
          retriever=None, runner_error=None, classifier=None, exc=None):
    runner = ScriptedRunner(steps, text, error=runner_error)
    backend = sql_backend(rows=rows if rows is not None else [("Rayuela",), ("Ficciones",)],
                          columns=columns or ["titulo"], exc=exc)
    agent = LibraryAgent(
        classifier=classifier or FakeClassifier(label, language),
        sql_backend=backend,
        retriever=retriever or FakeRetriever(),
        runner=runner,
    )
    return agent, runner, backend


# --- entrada (R-1.2) ---


@pytest.mark.parametrize("question", ["", "   ", "\n\t "])
def test_empty_question_is_rejected_without_calling_anything(question: str) -> None:
    classifier = FakeClassifier("sql")
    agent, runner, _ = build(classifier=classifier)
    with pytest.raises(EmptyQuestionError):
        agent.answer(question)
    assert classifier.questions == [] and runner.calls == 0


# --- clasificación previa y herramientas por fuente (R-2.7, D3) ---


def test_classification_is_resolved_before_any_tool() -> None:
    agent, _, _ = build("sql", steps=[("execute_sql", GOOD_SQL)])
    answer = agent.answer("¿Qué libros tiene Ana?")
    assert answer.trace[0] == "classification"
    assert answer.trace == ["classification", "execute_sql"]
    assert answer.classified_before_tools


@pytest.mark.parametrize(
    "label, offered",
    [("sql", ["execute_sql"]), ("rag", ["retrieve_documents"]),
     ("hybrid", ["execute_sql", "retrieve_documents"])],
)
def test_only_the_tools_of_the_classified_source_are_offered(label: str, offered: list[str]) -> None:
    # R-2.2 / R-2.3: una consulta `sql` no invoca RAG y viceversa.
    agent, runner, _ = build(label)
    agent.answer("consulta")
    assert runner.offered == offered


def test_the_system_prompt_carries_classification_dates_and_limits() -> None:
    agent, runner, _ = build("sql")
    agent.answer("consulta")
    cfg = load_config()
    assert "**sql**" in runner.system_prompt
    assert cfg.cuatrimestre_start.isoformat() in runner.system_prompt
    assert cfg.cuatrimestre_end.isoformat() in runner.system_prompt
    assert runner.max_steps == cfg.max_steps


# --- none (R-2.5) ---


def test_none_declares_absence_without_calling_the_model_or_the_tools() -> None:
    agent, runner, backend = build("none")
    answer = agent.answer("¿Cuál es el precio del libro Rayuela?")
    assert runner.calls == 0 and backend._conn.executed == []
    assert answer.classification == "none" and answer.sources == []
    assert answer.answer_kind == "no_coverage"
    assert not _has_source_line(answer.answer)  # R-5.2: la ausencia se declara en `sources` y `answer_kind`
    assert answer.is_valid(), answer.violations()
    assert answer.trace == ["classification"]


def test_none_answers_in_english_when_the_question_is_english() -> None:
    agent, _, _ = build("none", language="en")
    answer = agent.answer("What is the price of the book?")
    assert answer.title == "Houston, we have a problem"
    assert answer.answer.startswith("I searched the database")
    assert not _has_source_line(answer.answer)


# --- sql (R-3.x, R-5.2, R-5.3) ---


def test_sql_answer_declares_source_and_shows_the_executed_statement() -> None:
    agent, _, backend = build("sql", steps=[("execute_sql", GOOD_SQL)])
    answer = agent.answer("¿Qué libros tiene Ana?")

    assert answer.sources == ["sql"]
    assert not _has_source_line(answer.answer)  # R-5.2: la fuente va en `sources`, no en el texto
    assert answer.evidence["rows"] == [{"titulo": "Rayuela"}, {"titulo": "Ficciones"}]
    # R-3.9: lo exhibido es la sentencia efectivamente ejecutada (normalizada), no la del modelo.
    assert answer.evidence["sql"] == backend._conn.executed[0]
    assert answer.evidence["sql_original"] == GOOD_SQL
    assert answer.is_valid(), answer.violations()


def test_evidence_comes_from_the_tools_not_from_the_model_text() -> None:
    # Art. 4: si el modelo afirma datos sin haber consultado, no hay respuesta con fuente.
    agent, _, _ = build("sql", steps=[], text="Ana tiene 40 libros.")
    answer = agent.answer("¿Cuántos libros tiene Ana?")
    assert answer.sources == [] and answer.answer_kind == "error"
    assert "40" not in answer.answer
    assert answer.is_valid(), answer.violations()


def test_empty_result_is_reported_without_inference() -> None:
    # R-3.8
    agent, _, _ = build("sql", steps=[("execute_sql", GOOD_SQL)], rows=[], text="No tiene préstamos.")
    answer = agent.answer("¿Qué libros tiene Ana?")
    assert answer.sources == ["sql"] and answer.evidence["rows"] == []
    assert answer.is_valid(), answer.violations()


def test_a_rejected_statement_is_regenerated_once_and_the_attempts_are_recorded() -> None:
    # R-3.10: primer rechazo, segundo intento válido.
    agent, runner, backend = build("sql", steps=[("execute_sql", BAD_SQL), ("execute_sql", GOOD_SQL)])
    answer = agent.answer("¿Qué libros tiene Ana?")

    first = json.loads(runner.observations[0])
    assert first["ok"] is False and first["error"] == "SQL_NOT_READONLY" and first["detail"]
    assert answer.evidence["attempts"] == 2
    assert answer.evidence["sql_errors"][0]["sql_original"] == BAD_SQL
    assert len(backend._conn.executed) == 1, "el rechazado no llegó a la base"
    assert answer.sources == ["sql"]


def test_attempts_are_capped_by_the_tool_not_by_the_prompt() -> None:
    # D8: tras 2 rechazos la herramienta no vuelve a ejecutar aunque el modelo insista.
    agent, runner, backend = build(
        "sql", steps=[("execute_sql", BAD_SQL)] * 4, text="Hay 99 préstamos."
    )
    answer = agent.answer("borrá los préstamos")

    assert json.loads(runner.observations[2])["error"] == "ATTEMPTS_EXHAUSTED"
    assert backend._conn.executed == []
    # R-5.7: se informa el motivo con plantilla fija; el texto del modelo no se muestra.
    assert answer.answer_kind == "error" and answer.sources == []
    assert "SQL_NOT_READONLY" in answer.answer and "99" not in answer.answer
    assert len(answer.evidence["sql_errors"]) == 2
    assert answer.is_valid(), answer.violations()


def test_truncated_result_is_declared_in_the_answer() -> None:
    limit = load_config().max_rows
    rows = [(i,) for i in range(limit + 5)]
    agent, _, _ = build("sql", steps=[("execute_sql", GOOD_SQL)], rows=rows, columns=["id"])
    answer = agent.answer("listá todos")
    assert answer.evidence["truncated"] is True
    assert f"limitó a {limit} filas" in answer.answer


def test_a_database_failure_is_reported_not_papered_over() -> None:
    agent, _, _ = build("sql", steps=[("execute_sql", GOOD_SQL)], exc=Exception("conexión caída"))
    answer = agent.answer("¿Qué libros tiene Ana?")
    assert answer.answer_kind == "error" and "EXECUTION_ERROR" in answer.answer
    assert answer.sources == []


# --- rag (R-4.x, R-5.4) ---


def test_rag_answer_cites_document_and_location() -> None:
    agent, runner, _ = build("rag", steps=[("retrieve_documents", "plazo devolución")],
                             text="El plazo es de 15 días (Art. 12).")
    answer = agent.answer("¿Cuántos días tengo para devolver un libro?")
    assert answer.sources == ["rag"]
    assert answer.evidence["chunks"][0]["document"] == "reglamento_biblioteca.pdf"
    assert answer.evidence["chunks"][0]["location"] == "Art. 12"
    # R-5.4: el fragmento citado viaja con su texto para que el cliente lo exhiba.
    assert answer.evidence["chunks"][0]["text"]
    assert json.loads(runner.observations[0])["chunks"][0]["location"] == "Art. 12"
    assert not _has_source_line(answer.answer)
    assert answer.is_valid(), answer.violations()


@pytest.mark.parametrize("language", ["es", "en"])
def test_the_answer_declares_the_language_of_the_question(language) -> None:
    # R-5.1: la evidencia registra el idioma con el que se compuso la respuesta (el enunciado pide
    # castellano o inglés). La fuente no viaja en el texto (R-5.2, D84): solo en `sources`.
    agent, _, _ = build("sql", steps=[("execute_sql", GOOD_SQL)], language=language)

    answer = agent.answer("Which books are on loan?" if language == "en" else "¿Qué libros hay prestados?")

    assert answer.evidence["language"] == language
    assert answer.sources == ["sql"]
    assert not _has_source_line(answer.answer)


@pytest.mark.parametrize("model_line", ["Fuente: SQL", "Source: SQL", "fuentes: SQL + RAG"])
def test_a_source_line_written_by_the_model_is_removed_from_the_answer(model_line) -> None:
    # R-5.2: el texto no repite la fuente aunque el modelo la escriba; la declarada sigue siendo la de
    # las herramientas invocadas.
    agent, _, _ = build("sql", steps=[("execute_sql", GOOD_SQL)], text=f"Tiene 2 libros.\n\n{model_line}")

    answer = agent.answer("¿Qué libros tiene Ana?")

    assert answer.answer == "Tiene 2 libros."
    assert answer.sources == ["sql"]


@pytest.mark.parametrize(
    ("model_text", "expected"),
    [
        ('*El Hobbit* es una novela.\n\n(Fuente: *resenas_tolkien.pdf*, secciones "El Hobbit: sinopsis")',
         "*El Hobbit* es una novela."),
        ("El plazo es de 14 días (reglamento_biblioteca.pdf, Artículo 2. Plazos de préstamo).",
         "El plazo es de 14 días."),
        ("Hay 10 cómics. (Source: SQL)", "Hay 10 cómics."),
        ("Se renueva una vez (si no hay reserva).", "Se renueva una vez (si no hay reserva)."),
    ],
)
def test_a_parenthetical_source_citation_is_removed_from_the_answer(model_text: str, expected: str) -> None:
    # R-5.2, D84: ni la línea de fuente ni la cita entre paréntesis (con "Fuente:" o el nombre de un documento)
    # llegan al texto; un paréntesis común se conserva.
    agent, _, _ = build("sql", steps=[("execute_sql", GOOD_SQL)], text=model_text)

    answer = agent.answer("¿Qué libros tiene Ana?")

    assert answer.answer == expected


def test_the_detected_language_reaches_the_model_prompt() -> None:
    # La etiqueta fija sale en inglés por plantilla, pero la prosa la escribe el modelo: el prompt
    # instruye el idioma; sin esa instrucción el modelo tiende al castellano.
    agent, runner, _ = build("sql", steps=[("execute_sql", GOOD_SQL)], language="en")

    agent.answer("Which books are on loan?")

    assert "Answer in English" in runner.system_prompt
    assert "Respondé en castellano" not in runner.system_prompt


def test_a_gap_answer_in_english_declares_the_language_too() -> None:
    agent, _, _ = build("none", language="en")

    answer = agent.answer("What is the price of this book?")

    assert answer.evidence["language"] == "en"
    assert answer.sources == [] and not _has_source_line(answer.answer)


def test_rag_without_relevant_results_declares_no_coverage() -> None:
    # R-4.6: el agente no fabrica una respuesta.
    empty = FakeRetriever(RagResult(chunks=[], error=NO_RELEVANT_RESULTS, latency_ms=1))
    agent, _, _ = build("rag", steps=[("retrieve_documents", "precio")], retriever=empty,
                        text="Cuesta 20 dólares.")
    answer = agent.answer("¿Cuánto cuesta el reglamento?")
    assert answer.answer_kind == "no_coverage" and answer.sources == []
    assert "20" not in answer.answer
    assert answer.is_valid(), answer.violations()


def test_retrieval_failure_is_an_error_not_an_absence() -> None:
    broken = FakeRetriever(RagResult(chunks=[], error=RETRIEVAL_ERROR, latency_ms=1))
    agent, _, _ = build("rag", steps=[("retrieve_documents", "plazo")], retriever=broken)
    answer = agent.answer("¿Cuántos días tengo para devolver un libro?")
    assert answer.answer_kind == "error" and RETRIEVAL_ERROR in answer.answer


# --- hybrid (R-2.4, R-5.5) ---


def test_hybrid_invokes_both_tools_and_declares_both_sources() -> None:
    agent, _, _ = build(
        "hybrid", steps=[("execute_sql", GOOD_SQL), ("retrieve_documents", "multa")],
        text="Hecho: 20 días de préstamo. Conclusión: corresponde multa.",
    )
    answer = agent.answer("¿Le corresponde multa?")
    assert answer.sources == ["sql", "rag"]
    assert answer.trace == ["classification", "execute_sql", "retrieve_documents"]
    assert not _has_source_line(answer.answer)
    assert answer.is_valid(), answer.violations()


def test_hybrid_missing_a_source_declares_the_one_actually_invoked() -> None:
    # R-2.7: la fuente declarada es la efectivamente invocada y la inconsistencia se registra.
    agent, _, _ = build("hybrid", steps=[("execute_sql", GOOD_SQL)], text="Tiene un préstamo.")
    answer = agent.answer("¿Le corresponde multa?")
    assert answer.sources == ["sql"]
    assert answer.evidence["inconsistency"] == {"classified": "hybrid", "invoked": ["sql"]}
    assert not answer.is_valid(), "un híbrido sin las dos fuentes no cumple R-2.4"


def test_hybrid_does_not_conclude_when_the_rule_is_missing() -> None:
    empty = FakeRetriever(RagResult(chunks=[], error=NO_RELEVANT_RESULTS, latency_ms=1))
    agent, _, _ = build("hybrid", steps=[("execute_sql", GOOD_SQL), ("retrieve_documents", "multa")],
                        retriever=empty, text="Tiene un préstamo.")
    answer = agent.answer("¿Le corresponde multa?")
    assert "no es posible concluir" in answer.answer
    assert answer.sources == ["sql"]


# --- fallos del modelo y del clasificador (R-5.7) ---


def test_a_runner_failure_is_reported() -> None:
    agent, _, _ = build("sql", runner_error=TimeoutError("30s"))
    answer = agent.answer("¿Qué libros tiene Ana?")
    assert answer.answer_kind == "error" and "TimeoutError" in answer.answer
    assert answer.is_valid(), answer.violations()


def test_a_runner_failure_after_a_successful_tool_keeps_the_evidence_out_of_the_answer() -> None:
    agent, _, _ = build("sql", steps=[("execute_sql", GOOD_SQL)], text="")
    answer = agent.answer("¿Qué libros tiene Ana?")
    assert answer.answer_kind == "error"
    assert answer.evidence["rows"], "la evidencia obtenida se conserva para la traza"


def test_a_classifier_failure_is_an_error_answer_not_a_guess() -> None:
    agent, runner, _ = build(classifier=FakeClassifier(error=ClassificationError("clasificación inválida")))
    answer = agent.answer("¿Qué libros tiene Ana?")
    assert answer.answer_kind == "error" and runner.calls == 0
    assert answer.is_valid(), answer.violations()


# --- identificación del modelo (R-6.5, R-2.8) ---


def _with_config(agent: LibraryAgent, **overrides) -> LibraryAgent:
    agent.cfg = replace(agent.cfg, **overrides)
    return agent


def test_every_answer_records_the_model_that_produced_it() -> None:
    agent, _, _ = build("sql", steps=[("execute_sql", GOOD_SQL)])
    for answer in (agent.answer("¿Qué libros tiene Ana?"), build("none")[0].answer("¿Precio?")):
        assert answer.evidence["model"] == {"id": load_config().llm_model, "endpoint": "api"}


def test_a_local_endpoint_is_flagged_so_it_cannot_pass_as_acceptance_evidence(monkeypatch) -> None:
    monkeypatch.setenv("LLM_API_KEY", "clave-secreta-local")
    agent, _, _ = build("sql", steps=[("execute_sql", GOOD_SQL)])
    _with_config(agent, llm_model="openai/qwen-local", llm_api_base="http://127.0.0.1:8080/v1")
    answer = agent.answer("¿Qué libros tiene Ana?")

    assert answer.evidence["model"] == {"id": "openai/qwen-local", "endpoint": "local"}
    # R-6.5: ni la clave ni la URL completa se registran.
    dumped = json.dumps(answer.evidence, default=str)
    assert "clave-secreta-local" not in dumped and "127.0.0.1" not in dumped


def test_the_flow_is_identical_with_a_local_provider() -> None:
    # R-2.8: cambiar de proveedor no cambia clasificación previa, tools expuestas ni composición.
    local, runner, _ = build("hybrid", steps=[("execute_sql", GOOD_SQL), ("retrieve_documents", "multa")])
    _with_config(local, llm_model="openai/qwen-local", llm_api_base="http://127.0.0.1:8080/v1")
    remote, _, _ = build("hybrid", steps=[("execute_sql", GOOD_SQL), ("retrieve_documents", "multa")])

    a, b = local.answer("¿Le corresponde multa?"), remote.answer("¿Le corresponde multa?")
    assert (a.classification, a.sources, a.trace, a.answer_kind) == (b.classification, b.sources, b.trace, b.answer_kind)
    assert runner.offered == ["execute_sql", "retrieve_documents"]


# --- el orquestador no depende de smolagents ni de la red (Art. 6) ---


def test_importing_the_orchestrator_does_not_load_smolagents_or_google() -> None:
    root = Path(__file__).resolve().parents[1]
    code = (
        f"import sys; sys.path.insert(0, {str(root)!r}); import agent.agent; "
        "print(sorted(m for m in ('smolagents', 'litellm', 'google.genai', 'psycopg2') if m in sys.modules))"
    )
    out = subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, text=True, check=True)
    assert out.stdout.strip() == "[]", out.stdout


def test_make_chunk_helper_builds_a_valid_chunk() -> None:
    assert make_chunk(similarity=0.5).similarity == 0.5


def test_concurrent_answers_are_serialized() -> None:
    """Dos sesiones simultáneas no pueden usar a la vez las conexiones compartidas del agente."""
    import threading
    import time

    from agent.agent import LibraryAgent

    agent = LibraryAgent.__new__(LibraryAgent)
    agent._lock = threading.Lock()
    active, peak = 0, 0

    def fake_resolve(text, *_):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        time.sleep(0.05)
        active -= 1
        return None

    agent._resolve = fake_resolve
    agent._persist = lambda result, latency: result
    threads = [threading.Thread(target=agent.answer, args=("hola",)) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert peak == 1


def test_two_concurrent_answers_do_not_overlap_in_the_model_call() -> None:
    """R-1.3, D77: dos consultas no se solapan en la llamada al modelo (flujo real del agente).

    Determinista: sin `sleep` y sin reloj de pared. La primera consulta entra al modelo y queda ahí
    hasta que el test comprueba que la segunda no pudo entrar; recién entonces se la suelta.
    """
    import threading

    from agent.agent import LibraryAgent
    from tests.fakes import FakeClassifier, FakeRetriever, sql_backend

    entered: list[str] = []
    active: list[str] = []
    peak: list[int] = []
    first_in_model = threading.Event()
    let_first_leave = threading.Event()

    class QueuedModel:
        def run(self, *, question, system_prompt, tools, max_steps, on_event=None, cancel=None):
            active.append(question)
            peak.append(len(active))
            entered.append(question)
            if question == "primera":
                first_in_model.set()
                let_first_leave.wait(10.0)
            active.remove(question)
            return "Respuesta."

    agent = LibraryAgent(
        classifier=FakeClassifier("sql"),
        sql_backend=sql_backend(),
        retriever=FakeRetriever(),
        runner=QueuedModel(),
    )

    first = threading.Thread(target=agent.answer, args=("primera",))
    first.start()
    assert first_in_model.wait(10.0), "la primera consulta no entró a la llamada al modelo"

    second = threading.Thread(target=agent.answer, args=("segunda",))
    second.start()
    # El lock real está tomado por la primera: la segunda no puede entrar al modelo.
    assert agent._lock.acquire(blocking=False) is False, "la segunda entró mientras la primera trabajaba"

    let_first_leave.set()
    first.join(10.0)
    second.join(10.0)

    assert entered == ["primera", "segunda"]
    assert peak == [1, 1]


def test_progress_events_follow_the_flow_in_order() -> None:
    agent, _, _ = build("sql", steps=[("execute_sql", GOOD_SQL)])
    events: list[tuple[str, dict]] = []
    agent.answer("¿Qué libros tiene Ana?", on_event=lambda name, data: events.append((name, data)))

    assert [name for name, _ in events] == ["classified", "tool_call", "tool_result", "composing"]
    assert events[0][1]["classification"] == "sql"
    assert events[1][1] == {"tool": "execute_sql", "sql": GOOD_SQL}
    assert events[2][1]["ok"] is True and events[2][1]["rows"] == 2


def test_a_rejected_statement_is_reported_as_a_failed_tool_result() -> None:
    agent, _, _ = build("sql", steps=[("execute_sql", BAD_SQL)])
    events: list[tuple[str, dict]] = []
    agent.answer("borrá todo", on_event=lambda name, data: events.append((name, data)))

    result = next(data for name, data in events if name == "tool_result")
    assert result["ok"] is False and result["error"]


def test_a_cancelled_question_raises_and_records_nothing() -> None:
    import threading

    from agent.agent import AnswerCancelled
    from agent.runs import InMemoryRunRecorder

    recorder = InMemoryRunRecorder()
    agent, runner, _ = build("sql", steps=[("execute_sql", GOOD_SQL)])
    agent._recorder, agent._recorder_resolved = recorder, True
    cancel = threading.Event()
    cancel.set()
    with pytest.raises(AnswerCancelled):
        agent.answer("¿Qué libros tiene Ana?", cancel=cancel)
    assert runner.calls == 0
    assert not recorder.records


def test_cancelling_during_the_run_discards_the_answer() -> None:
    import threading

    from agent.agent import AnswerCancelled

    agent, _, _ = build("sql", steps=[("execute_sql", GOOD_SQL)])
    cancel = threading.Event()
    with pytest.raises(AnswerCancelled):
        agent.answer("q", on_event=lambda n, d: cancel.set() if n == "tool_result" else None, cancel=cancel)


# --- pedidos de escritura y notas (D94) ---


@pytest.mark.parametrize(
    ("language", "question", "start"),
    [("es", "Eliminá el libro El Hobbit", "¡No pasarás!"), ("en", "Delete all the loans", "You shall not pass!")],
)
def test_a_write_request_is_denied_without_touching_the_model_or_the_database(language, question, start) -> None:
    agent, runner, backend = build(classifier=FakeClassifier("none", language, write_request=True))
    answer = agent.answer(question)
    assert answer.title.startswith(start)
    assert start not in answer.answer  # la frase va en el título, no en el cuerpo (R-5.9)
    assert runner.calls == 0 and backend._conn.executed == []
    assert answer.sources == [] and answer.answer_kind == "no_coverage"
    assert answer.evidence["write_request"] is True
    assert answer.is_valid(), answer.violations()


def test_a_write_request_is_denied_even_if_the_label_is_not_none() -> None:
    agent, runner, _ = build(classifier=FakeClassifier("sql", write_request=True))
    answer = agent.answer("Borrá la reseña de Alas de sangre")
    assert runner.calls == 0 and answer.title.startswith("¡No pasarás!")


def test_a_truncated_result_has_a_single_note_even_if_the_model_wrote_its_own() -> None:
    limit = load_config().max_rows
    rows = [(i,) for i in range(limit + 5)]
    body = "Los libros son estos."
    model_text = f"{body}\n\n*(Nota: La lista muestra los primeros {limit} resultados encontrados).*"
    agent, _, _ = build("sql", steps=[("execute_sql", GOOD_SQL)], text=model_text, rows=rows, columns=["id"])
    answer = agent.answer("listá todos").answer
    assert answer.startswith(body)
    assert answer.lower().count("nota") == 1 and f"limitó a {limit} filas" in answer


def test_a_note_written_by_the_model_is_kept_when_the_system_adds_none() -> None:
    text = "Hay 2 libros.\n\nNota: es un dato de hoy."
    agent, _, _ = build("sql", steps=[("execute_sql", GOOD_SQL)], text=text)
    assert "Nota: es un dato de hoy." in agent.answer("¿cuántos?").answer


def test_a_normal_answer_has_no_title() -> None:
    agent, _, _ = build("sql", steps=[("execute_sql", GOOD_SQL)])
    assert agent.answer("¿Qué libros hay?").title is None


def test_an_error_keeps_its_technical_detail_in_the_body_and_the_phrase_in_the_title() -> None:
    agent, _, _ = build("sql", steps=[("execute_sql", GOOD_SQL)], exc=Exception("conexión caída"))
    answer = agent.answer("¿Qué libros tiene Ana?")
    assert answer.answer_kind == "error" and answer.title == "Houston, tenemos un problema"
    assert "Houston" not in answer.answer
