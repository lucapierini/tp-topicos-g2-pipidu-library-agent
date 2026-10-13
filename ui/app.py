"""Interfaz Streamlit (T8.1–T8.3, D17, D18): llama al agente en el mismo proceso, sin endpoint.

El historial es solo visual (`st.session_state`): cada consulta es independiente (D17).
"""
from __future__ import annotations

import streamlit as st

from agent.agent import EmptyQuestionError, answer
from agent.contracts import ANSWER_KIND_ERROR, ANSWER_KIND_NO_COVERAGE


def render_answer(result) -> None:
    if result.answer_kind == ANSWER_KIND_ERROR:
        st.error(result.answer)
    elif result.answer_kind == ANSWER_KIND_NO_COVERAGE:
        st.info(result.answer)
    else:
        st.write(result.answer)

    evidence = result.evidence or {}
    sql = evidence.get("sql")
    chunks = evidence.get("chunks") or []
    if sql or chunks:
        with st.expander("Evidencia"):
            if sql:
                st.code(sql, language="sql")
            for chunk in chunks:
                st.caption(f'{chunk.get("document")} · {chunk.get("location")}')


def main() -> None:
    st.set_page_config(page_title="Agente de biblioteca", page_icon="📚")
    st.title("Agente de biblioteca")
    history = st.session_state.setdefault("history", [])

    with st.form("consulta", clear_on_submit=True):
        question = st.text_input("Consulta")
        submitted = st.form_submit_button("Preguntar")

    if submitted:
        try:
            with st.spinner("Consultando…"):  # tarda de 3 a 170 s según la cuota
                result = answer(question)
        except EmptyQuestionError:  # R-1.2: no se invoca el agente
            st.warning("Escribí una consulta.")
        else:
            history.append(result)

    for result in reversed(history):
        with st.container(border=True):
            st.markdown(f"**{result.question}**")
            render_answer(result)


main()
