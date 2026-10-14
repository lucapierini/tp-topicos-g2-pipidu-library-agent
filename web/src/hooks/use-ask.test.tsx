import { act, renderHook, waitFor } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"
import { askReducer, initialState, useAsk } from "./use-ask"

const enc = new TextEncoder()
const sse = (event: string, data: object) => `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`
const RESULT = {
  question: "q",
  classification: "sql",
  sources: ["SQL"],
  answer: "ok",
  evidence: {},
  run_id: 1,
  answer_kind: "answer",
}

function mockFetch(text: string, status = 200) {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(enc.encode(text), { status })))
}

afterEach(() => vi.unstubAllGlobals())

describe("askReducer", () => {
  it("el progreso no declara fuentes: solo `done` tiene sources", () => {
    let s = askReducer(initialState, { type: "submit", question: "q" })
    s = askReducer(s, { type: "event", event: { type: "classified", classification: "sql" } })
    expect(s.status).toBe("running")
    expect("sources" in s).toBe(false)
    s = askReducer(s, { type: "event", event: { type: "result", result: RESULT as never } })
    expect(s.status === "done" && s.result.sources).toEqual(["SQL"])
  })

  it("el heartbeat actualiza los segundos sin sumar progreso", () => {
    let s = askReducer(initialState, { type: "submit", question: "q" })
    s = askReducer(s, { type: "event", event: { type: "heartbeat", elapsed_s: 10 } })
    expect(s.status === "running" && s.elapsed).toBe(10)
    expect(s.status === "running" && s.progress).toEqual([])
  })
})

describe("useAsk", () => {
  it("resuelve una consulta: running → done", async () => {
    mockFetch(sse("start", { question: "q" }) + sse("result", RESULT))
    const { result } = renderHook(() => useAsk())
    act(() => void result.current.ask("  hola  "))
    await waitFor(() => expect(result.current.state.status).toBe("done"))
    expect(JSON.parse((fetch as ReturnType<typeof vi.fn>).mock.calls[0][1].body)).toEqual({ question: "hola" })
  })

  it("no llama a la API con una consulta vacía", async () => {
    mockFetch("")
    const { result } = renderHook(() => useAsk())
    await act(async () => result.current.ask("   "))
    expect(fetch).not.toHaveBeenCalled()
    expect(result.current.state.status).toBe("idle")
  })

  it("un flujo sin result termina en failed/incomplete", async () => {
    mockFetch(sse("classified", { classification: "sql" }))
    const { result } = renderHook(() => useAsk())
    await act(async () => result.current.ask("q"))
    expect(result.current.state).toMatchObject({ status: "failed", kind: "incomplete" })
  })

  it("el evento error termina en failed/agent", async () => {
    mockFetch(sse("error", { detail: "Boom" }))
    const { result } = renderHook(() => useAsk())
    await act(async () => result.current.ask("q"))
    expect(result.current.state).toMatchObject({ status: "failed", kind: "agent", message: "Boom" })
  })

  it("distingue API caída de consulta rechazada", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => Promise.reject(new TypeError("down"))))
    const { result } = renderHook(() => useAsk())
    await act(async () => result.current.ask("q"))
    expect(result.current.state).toMatchObject({ status: "failed", kind: "unreachable" })
    mockFetch("", 422)
    await act(async () => result.current.ask("q"))
    expect(result.current.state).toMatchObject({ status: "failed", kind: "invalid" })
  })

  it("cancelar corta la conexión y vuelve a idle sin respuesta", async () => {
    let signal: AbortSignal | undefined
    vi.stubGlobal(
      "fetch",
      vi.fn((_u: string, init: RequestInit) => {
        signal = init.signal ?? undefined
        return new Promise<Response>((_res, rej) =>
          init.signal?.addEventListener("abort", () => rej(new DOMException("aborted", "AbortError")))
        )
      })
    )
    const { result } = renderHook(() => useAsk())
    act(() => void result.current.ask("q"))
    await waitFor(() => expect(result.current.state.status).toBe("running"))
    act(() => result.current.cancel())
    expect(signal?.aborted).toBe(true)
    expect(result.current.state).toEqual({ status: "idle" })
    await act(async () => {}) // deja resolver el catch de la consulta cancelada
    expect(result.current.state).toEqual({ status: "idle" })
  })
})
