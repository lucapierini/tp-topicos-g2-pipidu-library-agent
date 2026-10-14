import { describe, expect, it } from "vitest"
import { AskHttpError, SseParser, askStream, type AskEvent } from "./ask-stream"

const enc = new TextEncoder()

function streamOf(chunks: Uint8Array[]): ReadableStream<Uint8Array> {
  return new ReadableStream({
    start(controller) {
      for (const c of chunks) controller.enqueue(c)
      controller.close()
    },
  })
}

function fakeFetch(body: ReadableStream<Uint8Array>, status = 200): typeof fetch {
  return (async () => new Response(body, { status })) as typeof fetch
}

async function collect(gen: AsyncGenerator<AskEvent>): Promise<AskEvent[]> {
  const out: AskEvent[] = []
  for await (const e of gen) out.push(e)
  return out
}

const sse = (event: string, data: object) => `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`

describe("SseParser", () => {
  it("junta un evento partido entre chunks", () => {
    const p = new SseParser()
    expect(p.push('event: classified\ndata: {"classif')).toEqual([])
    expect(p.push('ication": "sql"}\n\n')).toEqual([
      { event: "classified", data: '{"classification": "sql"}' },
    ])
  })

  it("separa varios eventos de un mismo chunk y tolera CRLF", () => {
    const p = new SseParser()
    const out = p.push('event: a\r\ndata: {"x":1}\r\n\r\nevent: b\r\ndata: {"y":2}\r\n\r\n')
    expect(out.map((e) => e.event)).toEqual(["a", "b"])
  })
})

describe("askStream", () => {
  it("emite los eventos en orden y termina con result", async () => {
    const result = {
      question: "q",
      classification: "sql",
      sources: ["SQL"],
      answer: "ok",
      evidence: { sql: "SELECT 1", rows: [{ vence: "2026-10-01", multa: "12.50" }] },
      run_id: 7,
      answer_kind: "answer",
    }
    const text = sse("start", { question: "q" }) + sse("classified", { classification: "sql" }) + sse("result", result)
    const events = await collect(askStream("q", { fetchImpl: fakeFetch(streamOf([enc.encode(text)])) }))
    expect(events.map((e) => e.type)).toEqual(["start", "classified", "result"])
    const last = events[2]
    expect(last.type === "result" && last.result.evidence.rows?.[0]).toEqual({ vence: "2026-10-01", multa: "12.50" })
  })

  it("decodifica UTF-8 aunque un carácter quede partido entre chunks", async () => {
    const bytes = enc.encode(sse("error", { detail: "canción" }))
    const cut = bytes.indexOf(0xc3) + 1 // parte la "ó"
    const events = await collect(
      askStream("q", { fetchImpl: fakeFetch(streamOf([bytes.slice(0, cut), bytes.slice(cut)])) })
    )
    expect(events).toEqual([{ type: "error", detail: "canción" }])
  })

  it("entrega el evento error", async () => {
    const events = await collect(
      askStream("q", { fetchImpl: fakeFetch(streamOf([enc.encode(sse("error", { detail: "Boom" }))])) })
    )
    expect(events).toEqual([{ type: "error", detail: "Boom" }])
  })

  it("ignora eventos desconocidos", async () => {
    const events = await collect(
      askStream("q", { fetchImpl: fakeFetch(streamOf([enc.encode(sse("otro", { a: 1 }) + sse("composing", {}))])) })
    )
    expect(events).toEqual([{ type: "composing" }])
  })

  it("distingue API inalcanzable, 422 y otros errores HTTP", async () => {
    const down = (async () => {
      throw new TypeError("Failed to fetch")
    }) as typeof fetch
    await expect(collect(askStream("q", { fetchImpl: down }))).rejects.toMatchObject({ kind: "unreachable" })
    await expect(collect(askStream("q", { fetchImpl: fakeFetch(streamOf([]), 422) }))).rejects.toMatchObject({
      kind: "invalid",
    })
    await expect(collect(askStream("q", { fetchImpl: fakeFetch(streamOf([]), 500) }))).rejects.toBeInstanceOf(
      AskHttpError
    )
  })

  it("propaga el aborto sin convertirlo en error de conexión", async () => {
    const ctrl = new AbortController()
    ctrl.abort()
    const aborting = (async (_u: unknown, init?: RequestInit) => {
      if (init?.signal?.aborted) throw new DOMException("aborted", "AbortError")
      return new Response()
    }) as typeof fetch
    await expect(collect(askStream("q", { signal: ctrl.signal, fetchImpl: aborting }))).rejects.toMatchObject({
      name: "AbortError",
    })
  })
})
