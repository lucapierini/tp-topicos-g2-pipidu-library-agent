import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest"
import { App } from "./App"

const enc = new TextEncoder()
const sse = (event: string, data: object) => `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`
const RESULT = {
  question: "How long is a loan?",
  classification: "rag",
  sources: ["RAG"],
  answer: "A loan lasts 14 days.",
  evidence: {},
  run_id: 2,
  answer_kind: "answer",
}

beforeAll(() => {
  // jsdom no trae estas APIs, que usa el MessageScroller.
  globalThis.ResizeObserver ??= class {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
  globalThis.IntersectionObserver ??= class {
    observe() {}
    unobserve() {}
    disconnect() {}
    takeRecords() {
      return []
    }
    root = null
    rootMargin = ""
    thresholds = []
  } as unknown as typeof IntersectionObserver
  Element.prototype.scrollTo ??= () => {}
  Element.prototype.scrollIntoView ??= () => {}
})

afterEach(() => vi.unstubAllGlobals())

describe("App", () => {
  it("envía la consulta en inglés sin modificarla y muestra la respuesta tal como llega (R-8.7)", async () => {
    const fetchMock = vi.fn(async () => new Response(enc.encode(sse("result", RESULT))))
    vi.stubGlobal("fetch", fetchMock)
    render(<App />)
    await userEvent.type(screen.getByLabelText("Consulta"), "How long is a loan?{Enter}")
    expect(await screen.findByText("A loan lasts 14 days.")).toBeInTheDocument()
    const body = JSON.parse((fetchMock.mock.calls[0] as unknown as [string, RequestInit])[1].body as string)
    expect(body).toEqual({ question: "How long is a loan?" })
  })

  it("cancelar no deja respuesta ni fuentes de la consulta cancelada (R-8.5)", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        (_url: string, init: RequestInit) =>
          new Promise<Response>((_res, rej) =>
            init.signal?.addEventListener("abort", () => rej(new DOMException("aborted", "AbortError")))
          )
      )
    )
    render(<App />)
    await userEvent.type(screen.getByLabelText("Consulta"), "algo{Enter}")
    await userEvent.click(await screen.findByRole("button", { name: "Cancelar" }))
    await waitFor(() => expect(screen.getByRole("button", { name: "Enviar" })).toBeInTheDocument())
    expect(screen.queryByText(/Fuente/)).not.toBeInTheDocument()
    expect(screen.getByText("Hacé una consulta")).toBeInTheDocument()
  })

  it("API caída: informa la conexión y permite reintentar (R-8.6)", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => Promise.reject(new TypeError("down"))))
    render(<App />)
    await userEvent.type(screen.getByLabelText("Consulta"), "hola{Enter}")
    expect(await screen.findByText("No se puede conectar con la API")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Reintentar" })).toBeInTheDocument()
  })

  it("422: indica que la consulta no es válida (R-8.6)", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response("{}", { status: 422 })))
    render(<App />)
    await userEvent.type(screen.getByLabelText("Consulta"), "hola{Enter}")
    expect(await screen.findByText("La consulta no es válida")).toBeInTheDocument()
  })

  it("un flujo que termina sin result informa que no se completó (R-8.6)", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(enc.encode(sse("classified", { classification: "sql" })))))
    render(<App />)
    await userEvent.type(screen.getByLabelText("Consulta"), "hola{Enter}")
    expect(await screen.findByText("La consulta no se completó")).toBeInTheDocument()
  })

  it("conserva las consultas y respuestas anteriores al enviar una nueva (R-8.10)", async () => {
    let n = 0
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        n += 1
        return new Response(enc.encode(sse("result", { ...RESULT, answer: `Respuesta ${n}` })))
      })
    )
    render(<App />)
    await userEvent.type(screen.getByLabelText("Consulta"), "primera{Enter}")
    expect(await screen.findByText("Respuesta 1")).toBeInTheDocument()
    await userEvent.type(screen.getByLabelText("Consulta"), "segunda{Enter}")
    expect(await screen.findByText("Respuesta 2")).toBeInTheDocument()
    expect(screen.getByText("primera")).toBeInTheDocument()
    expect(screen.getByText("Respuesta 1")).toBeInTheDocument()
    expect(screen.getByText("segunda")).toBeInTheDocument()
    // el agente recibe solo la consulta actual (R-7.0, D17)
    const calls = (fetch as ReturnType<typeof vi.fn>).mock.calls as unknown as [string, RequestInit][]
    expect(JSON.parse(calls[1][1].body as string)).toEqual({ question: "segunda" })
  })

  it("cancelar la segunda consulta no borra la primera (R-8.5, R-8.10)", async () => {
    let n = 0
    vi.stubGlobal(
      "fetch",
      vi.fn((_url: string, init: RequestInit) => {
        n += 1
        if (n === 1) return Promise.resolve(new Response(enc.encode(sse("result", RESULT))))
        return new Promise<Response>((_res, rej) =>
          init.signal?.addEventListener("abort", () => rej(new DOMException("aborted", "AbortError")))
        )
      })
    )
    render(<App />)
    await userEvent.type(screen.getByLabelText("Consulta"), "primera{Enter}")
    await screen.findByText("A loan lasts 14 days.")
    await userEvent.type(screen.getByLabelText("Consulta"), "segunda{Enter}")
    await userEvent.click(await screen.findByRole("button", { name: "Cancelar" }))
    await waitFor(() => expect(screen.getByRole("button", { name: "Enviar" })).toBeInTheDocument())
    expect(screen.getByText("A loan lasts 14 days.")).toBeInTheDocument()
    expect(screen.queryByText("segunda")).not.toBeInTheDocument()
  })
})
