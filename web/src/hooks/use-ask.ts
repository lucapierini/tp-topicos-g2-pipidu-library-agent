import { useCallback, useReducer, useRef } from "react"
import { AskHttpError, askStream, type AgentResult, type AskEvent } from "@/lib/ask-stream"

export type FailureKind = "unreachable" | "invalid" | "http" | "incomplete" | "agent"

export type AskState =
  | { status: "idle" }
  | { status: "running"; question: string; progress: AskEvent[]; elapsed: number }
  | { status: "done"; question: string; result: AgentResult }
  | { status: "failed"; question: string; kind: FailureKind; message: string }

type Action =
  | { type: "submit"; question: string }
  | { type: "event"; event: AskEvent }
  | { type: "closed" } // el flujo terminó sin `result` ni `error`
  | { type: "failure"; kind: FailureKind; message: string }
  | { type: "reset" }

export const initialState: AskState = { status: "idle" }

/** `sources` solo existe en `done`: el progreso nunca declara fuente (R-7.2, R-8.2). */
export function askReducer(state: AskState, action: Action): AskState {
  switch (action.type) {
    case "submit":
      return { status: "running", question: action.question, progress: [], elapsed: 0 }
    case "reset":
      return initialState
    case "failure":
      return state.status === "running"
        ? { status: "failed", question: state.question, kind: action.kind, message: action.message }
        : state
    case "closed":
      return state.status === "running"
        ? {
            status: "failed",
            question: state.question,
            kind: "incomplete",
            message: "La consulta no se completó: la conexión se cerró antes del resultado.",
          }
        : state
    case "event": {
      if (state.status !== "running") return state
      const { event } = action
      if (event.type === "result") return { status: "done", question: state.question, result: event.result }
      if (event.type === "error") {
        return { status: "failed", question: state.question, kind: "agent", message: event.detail }
      }
      if (event.type === "heartbeat") return { ...state, elapsed: event.elapsed_s }
      return { ...state, progress: [...state.progress, event] }
    }
  }
}

function describe(error: unknown): { kind: FailureKind; message: string } {
  if (error instanceof AskHttpError) return { kind: error.kind, message: error.message }
  return { kind: "http", message: "Ocurrió un error inesperado al consultar la API." }
}

export function useAsk(baseUrl?: string) {
  const [state, dispatch] = useReducer(askReducer, initialState)
  const controller = useRef<AbortController | null>(null)

  const ask = useCallback(
    async (raw: string) => {
      const question = raw.trim()
      if (!question || controller.current) return // vacía o ya hay una en curso (R-8.1)
      const ctrl = new AbortController()
      controller.current = ctrl
      dispatch({ type: "submit", question })
      try {
        let finished = false
        for await (const event of askStream(question, { signal: ctrl.signal, baseUrl })) {
          dispatch({ type: "event", event })
          if (event.type === "result" || event.type === "error") finished = true
        }
        if (!finished) dispatch({ type: "closed" })
      } catch (error) {
        if (ctrl.signal.aborted) return // cancelada: `cancel` ya volvió a `idle`
        dispatch({ type: "failure", ...describe(error) })
      } finally {
        if (controller.current === ctrl) controller.current = null
      }
    },
    [baseUrl]
  )

  /** Corta la conexión: la API cancela al agente (R-7.5). Sin respuesta parcial (R-8.5). */
  const cancel = useCallback(() => {
    controller.current?.abort()
    controller.current = null
    dispatch({ type: "reset" })
  }, [])

  const reset = useCallback(() => dispatch({ type: "reset" }), [])

  return { state, ask, cancel, reset }
}
