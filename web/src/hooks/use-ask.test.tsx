import { act, renderHook, waitFor } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"
import { askReducer, initialView, useAsk } from "./use-ask"

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
    let v = askReducer(initialView, { type: "submit", question: "q" })
    v = askReducer(v, { type: "event", event: { type: "classified", classification: "sql" } })
    expect(v.current.status).toBe("running")
    expect("sources" in v.current).toBe(false)
    v = askReducer(v, { type: "event", event: { type: "result", result: RESULT as never } })
    expect(v.current.status === "done" && v.current.result.sources).toEqual(["SQL"])
  })

  it("el heartbeat actualiza los segundos sin sumar progreso", () => {
    let v = askReducer(initialView, { type: "submit", question: "q" })
    v = askReducer(v, { type: "event", event: { type: "heartbeat", elapsed_s: 10 } })
    expect(v.current.status === "running" && v.current.elapsed).toBe(10)
    expect(v.current.status === "running" && v.current.progress).toEqual([])
  })

  it("una consulta nueva archiva la anterior en el historial en vez de borrarla (R-8.10)", () => {
    let v = askReducer(initialView, { type: "submit", question: "uno" })
    v = askReducer(v, { type: "event", event: { type: "result", result: RESULT as never } })
    v = askReducer(v, { type: "submit", question: "dos" })
    expect(v.history.map((t) => t.question)).toEqual(["uno"])
    expect(v.current).toMatchObject({ status: "running", question: "dos" })
  })

  it("reintentar una consulta fallida la reemplaza, no la duplica", () => {
    let v = askReducer(initialView, { type: "submit", question: "uno" })
    v = askReducer(v, { type: "failure", kind: "unreachable", message: "x" })
    v = askReducer(v, { type: "submit", question: "uno", retry: true })
    expect(v.history).toEqual([])
    expect(v.current.status).toBe("running")
  })

  it("cancelar descarta solo la consulta en curso y conserva el historial", () => {
    let v = askReducer(initialView, { type: "submit", question: "uno" })
    v = askReducer(v, { type: "event", event: { type: "result", result: RESULT as never } })
    v = askReducer(v, { type: "submit", question: "dos" })
    v = askReducer(v, { type: "reset" })
    expect(v.current).toEqual({ status: "idle" })
    expect(v.history.map((t) => t.question)).toEqual(["uno"])
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
