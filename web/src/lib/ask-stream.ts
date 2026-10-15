// Cliente de `POST /ask` (SSE). `EventSource` solo hace GET: se lee `response.body` a mano.

export type Classification = "sql" | "rag" | "hybrid" | "none"
export type AnswerKind = "answer" | "no_coverage" | "error"

export interface SqlEvidence {
  sql?: string | null
  rows?: Array<Record<string, unknown>>
  chunks?: Array<{ document: string; location: string; text?: string }>
}

export interface AgentResult {
  question: string
  classification: Classification
  sources: string[]
  answer: string
  evidence: SqlEvidence
  run_id: number | null
  answer_kind: AnswerKind
  title?: string | null
  trace?: string[]
}

export type AskEvent =
  | { type: "start"; question: string }
  | { type: "classified"; classification: Classification; language?: string }
  | { type: "tool_call"; tool: string; sql?: string; query?: string }
  | { type: "tool_result"; tool: string; ok: boolean; rows?: number; chunks?: number; error?: string }
  | { type: "composing" }
  | {
      type: "step"
      step: number
      duration_s: number
      input_tokens?: number
      output_tokens?: number
      tools?: string[]
    }
  | { type: "heartbeat"; elapsed_s: number }
  | { type: "result"; result: AgentResult }
  | { type: "error"; detail: string }

/** La API no responde o rechazó la consulta antes de abrir el flujo. */
export class AskHttpError extends Error {
  readonly kind: "unreachable" | "invalid" | "http"
  readonly status?: number

  constructor(kind: AskHttpError["kind"], message: string, status?: number) {
    super(message)
    this.name = "AskHttpError"
    this.kind = kind
    this.status = status
  }
}

interface RawEvent {
  event: string
  data: string
}

/** Acumula texto y devuelve los eventos completos (separados por línea en blanco). */
export class SseParser {
  private buffer = ""

  push(chunk: string): RawEvent[] {
    this.buffer += chunk.replace(/\r\n/g, "\n")
    const events: RawEvent[] = []
    let index: number
    while ((index = this.buffer.indexOf("\n\n")) !== -1) {
      const block = this.buffer.slice(0, index)
      this.buffer = this.buffer.slice(index + 2)
      const parsed = parseBlock(block)
      if (parsed) events.push(parsed)
    }
    return events
  }
}

function parseBlock(block: string): RawEvent | null {
  let event = "message"
  const data: string[] = []
  for (const line of block.split("\n")) {
    if (line.startsWith(":")) continue // comentario
    if (line.startsWith("event:")) event = line.slice(6).trim()
    else if (line.startsWith("data:")) data.push(line.slice(5).replace(/^ /, ""))
  }
  return data.length ? { event, data: data.join("\n") } : null
}

export function toAskEvent(raw: RawEvent): AskEvent | null {
  let data: Record<string, unknown>
  try {
    data = JSON.parse(raw.data)
  } catch {
    return null
  }
  switch (raw.event) {
    case "result":
      return { type: "result", result: data as unknown as AgentResult }
    case "error":
      return { type: "error", detail: String(data.detail ?? "") }
    case "composing":
      return { type: "composing" }
    case "start":
    case "classified":
    case "tool_call":
    case "tool_result":
    case "step":
    case "heartbeat":
      return { type: raw.event, ...data } as AskEvent
    default:
      return null // evento desconocido: se ignora
  }
}

export interface AskOptions {
  signal?: AbortSignal
  baseUrl?: string
  fetchImpl?: typeof fetch
}

/** Envía la consulta y entrega los eventos a medida que llegan. */
export async function* askStream(
  question: string,
  { signal, baseUrl = "/api", fetchImpl = fetch }: AskOptions = {}
): AsyncGenerator<AskEvent> {
  let response: Response
  try {
    response = await fetchImpl(`${baseUrl}/ask`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
      body: JSON.stringify({ question }),
      signal,
    })
  } catch (error) {
    if (signal?.aborted) throw error
    throw new AskHttpError("unreachable", "No se pudo conectar con la API.")
  }

  if (response.status === 422) {
    throw new AskHttpError("invalid", "La consulta no es válida.", 422)
  }
  if (!response.ok || !response.body) {
    throw new AskHttpError("http", `La API respondió ${response.status}.`, response.status)
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder("utf-8")
  const parser = new SseParser()
  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      for (const raw of parser.push(decoder.decode(value, { stream: true }))) {
        const event = toAskEvent(raw)
        if (event) yield event
      }
    }
    for (const raw of parser.push(decoder.decode() + "\n\n")) {
      const event = toAskEvent(raw)
      if (event) yield event
    }
  } finally {
    reader.cancel().catch(() => {})
  }
}
