import type { AskEvent } from "@/lib/ask-stream"

const CLASSIFICATION_LABEL: Record<string, string> = {
  sql: "la base de datos (SQL)",
  rag: "los documentos (RAG)",
  hybrid: "la base de datos y los documentos",
  none: "ninguna fuente",
}

/** Texto del progreso para una persona. `null` = el evento no se muestra. Nunca declara fuentes (R-8.2). */
export function describeEvent(event: AskEvent): string | null {
  switch (event.type) {
    case "classified":
      return `Clasificada: corresponde consultar ${CLASSIFICATION_LABEL[event.classification] ?? event.classification}`
    case "tool_call":
      return event.tool.toLowerCase().includes("sql") ? "Consultando la base de datos" : "Buscando en los documentos"
    case "tool_result": {
      if (!event.ok) return `La herramienta falló${event.error ? `: ${event.error}` : ""}`
      if (event.rows !== undefined) return `Devolvió ${event.rows} ${event.rows === 1 ? "fila" : "filas"}`
      if (event.chunks !== undefined) return `Encontró ${event.chunks} ${event.chunks === 1 ? "fragmento" : "fragmentos"}`
      return "La herramienta respondió"
    }
    case "composing":
      return "Armando la respuesta"
    default:
      return null // start, step, heartbeat, result, error
  }
}
