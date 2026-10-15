"""Cableado real con `smolagents` (D2), sin red: un `Model` falso emite tool-calls de verdad.

Verifica lo que los tests con `ScriptedRunner` no pueden: que los `ToolSpec` se adapten bien al
framework, que el system prompt llegue al modelo, que `final_answer` cierre el loop y que
`max_steps` corte un modelo que no converge.
"""
from __future__ import annotations

import json

import pytest

pytest.importorskip("smolagents")

from smolagents.models import (  # noqa: E402
    ChatMessage,
    ChatMessageToolCall,
    ChatMessageToolCallFunction,
    Model,
)

from agent.agent import LibraryAgent, SmolagentsRunner  # noqa: E402
from agent.config import load_config  # noqa: E402
from tests.fakes import FakeClassifier, FakeRetriever, sql_backend  # noqa: E402

GOOD_SQL = "SELECT l.titulo FROM prestamos p JOIN libros l ON l.id = p.libro_id"


def tool_call(name: str, **arguments) -> ChatMessage:
    return ChatMessage(
        role="assistant",
        content="",
        tool_calls=[
            ChatMessageToolCall(
                id=f"call_{name}",
                type="function",
                function=ChatMessageToolCallFunction(name=name, arguments=arguments),
            )
        ],
    )


class ScriptedModel(Model):
    """Responde con una secuencia fija de mensajes y registra lo que recibe."""

    def __init__(self, replies: list[ChatMessage]):
        super().__init__(model_id="scripted")
        self.replies = list(replies)
        self.seen: list[list[ChatMessage]] = []
        self.tool_names: list[list[str]] = []

    def generate(self, messages, stop_sequences=None, response_format=None, tools_to_call_from=None, **kwargs):
        self.seen.append(list(messages))
        self.tool_names.append([t.name for t in (tools_to_call_from or [])])
        return self.replies.pop(0) if len(self.replies) > 1 else self.replies[0]


def agent_with(model: ScriptedModel, label="sql", **backends) -> LibraryAgent:
    return LibraryAgent(
        classifier=FakeClassifier(label),
        sql_backend=backends.get("sql") or sql_backend(rows=[("Rayuela",)], columns=["titulo"]),
        retriever=backends.get("retriever") or FakeRetriever(),
        runner=SmolagentsRunner(load_config(), model=model),
    )


def test_full_loop_tool_call_then_final_answer() -> None:
    model = ScriptedModel([
        tool_call("execute_sql", sql=GOOD_SQL),
        tool_call("final_answer", answer="Ana tiene prestado Rayuela."),
    ])
    answer = agent_with(model).answer("¿Qué libros tiene Ana?")

    assert answer.sources == ["sql"]
    assert answer.evidence["rows"] == [{"titulo": "Rayuela"}]
    assert answer.answer.startswith("Ana tiene prestado Rayuela.")
    assert answer.trace == ["classification", "execute_sql"]
    assert answer.is_valid(), answer.violations()


def test_the_model_receives_our_system_prompt_and_only_the_classified_tools() -> None:
    model = ScriptedModel([tool_call("final_answer", answer="ok")])
    agent_with(model, label="rag").answer("¿Cuál es el horario?")

    first_call = model.seen[0]
    flattened = json.dumps([str(m.content) for m in first_call], ensure_ascii=False)
    assert "retrieve_documents" in flattened and "NO_RELEVANT_RESULTS" in flattened
    assert "execute_sql" not in model.tool_names[0]
    assert "retrieve_documents" in model.tool_names[0] and "final_answer" in model.tool_names[0]


def test_the_tool_observation_reaches_the_model() -> None:
    model = ScriptedModel([
        tool_call("execute_sql", sql="DELETE FROM prestamos"),
        tool_call("final_answer", answer="No se pudo."),
    ])
    agent_with(model).answer("borrá todo")

    second_call = json.dumps([str(m.content) for m in model.seen[1]], ensure_ascii=False)
    assert "SQL_NOT_READONLY" in second_call, "el modelo ve el motivo del rechazo para corregirlo"


def test_max_steps_cuts_a_model_that_never_converges() -> None:
    model = ScriptedModel([tool_call("execute_sql", sql=GOOD_SQL)])  # repite la misma tool para siempre
    agent = agent_with(model)
    answer = agent.answer("¿Qué libros tiene Ana?")

    # Al llegar a `max_steps` smolagents hace UNA llamada extra para pedir el cierre: el tope real
    # de llamadas al modelo es `max_steps + 1` (D15).
    assert len(model.seen) <= load_config().max_steps + 1
    # Hubo evidencia pero el modelo no cerró: no se presenta como respuesta con fuente (R-5.7).
    assert answer.answer_kind == "error"
    assert answer.is_valid(), answer.violations()


def test_step_events_come_from_the_framework_callbacks() -> None:
    model = ScriptedModel([
        tool_call("execute_sql", sql=GOOD_SQL),
        tool_call("final_answer", answer="Ana tiene prestado Rayuela."),
    ])
    events: list[tuple[str, dict]] = []
    agent_with(model).answer("¿Qué libros tiene Ana?", on_event=lambda n, d: events.append((n, d)))

    steps = [data for name, data in events if name == "step"]
    assert [s["step"] for s in steps] == [1, 2]
    assert steps[0]["tools"] == ["execute_sql"] and steps[1]["tools"] == ["final_answer"]
    assert all(isinstance(s["duration_s"], float) for s in steps)


def test_cancel_interrupts_the_framework_before_the_next_step() -> None:
    import threading

    from agent.agent import AnswerCancelled

    model = ScriptedModel([
        tool_call("execute_sql", sql=GOOD_SQL),
        tool_call("final_answer", answer="no debería llegar"),
    ])
    cancel = threading.Event()
    with pytest.raises(AnswerCancelled):
        agent_with(model).answer(
            "q", on_event=lambda n, d: cancel.set() if n == "step" else None, cancel=cancel,
        )
    assert len(model.seen) == 1  # el segundo paso nunca llamó al modelo
