import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it } from "vitest"
import type { AgentResult } from "@/lib/ask-stream"
import { AnswerView } from "./answer-view"

const base: AgentResult = {
  question: "q",
  classification: "sql",
  sources: ["SQL"],
  answer: "Hay 3 préstamos.",
  evidence: {},
  run_id: 1,
  answer_kind: "answer",
}

describe("AnswerView", () => {
  it("muestra la respuesta y cada fuente declarada (R-8.3)", () => {
    render(<AnswerView result={{ ...base, sources: ["SQL", "RAG"] }} />)
    expect(screen.getByText("Hay 3 préstamos.")).toBeInTheDocument()
    expect(screen.getByText("SQL")).toBeInTheDocument()
    expect(screen.getByText("RAG")).toBeInTheDocument()
  })

  it("no_coverage se presenta como ausencia de información, sin fuentes", () => {
    render(<AnswerView result={{ ...base, answer_kind: "no_coverage", sources: ["SQL"], answer: "No hay datos." }} />)
    expect(screen.getByText("Sin información suficiente")).toBeInTheDocument()
    expect(screen.queryByText("Fuente:")).not.toBeInTheDocument()
    expect(screen.queryByText("SQL")).not.toBeInTheDocument()
  })

  it("error se presenta como error, sin fuentes", () => {
    render(<AnswerView result={{ ...base, answer_kind: "error", sources: [], answer: "Falló la herramienta." }} />)
    expect(screen.getByText("El agente no pudo responder")).toBeInTheDocument()
    expect(screen.queryByText("Fuente:")).not.toBeInTheDocument()
  })

  it("usa el título del resultado como encabezado y deja el cuerpo adentro (R-5.9)", () => {
    render(
      <AnswerView
        result={{ ...base, answer_kind: "no_coverage", sources: [], title: "¡No pasarás! 🧙", answer: "Solo lectura." }}
      />,
    )
    expect(screen.getByText("¡No pasarás! 🧙")).toBeInTheDocument()
    expect(screen.getByText("Solo lectura.")).toBeInTheDocument()
    expect(screen.queryByText("Sin información suficiente")).not.toBeInTheDocument()
  })

  it("sin evidencia no ofrece la sección (R-8.4)", () => {
    render(<AnswerView result={{ ...base, evidence: {} }} />)
    expect(screen.queryByText("Ver evidencia")).not.toBeInTheDocument()
  })

  it("evidencia SQL: sentencia y filas tal como llegan (R-8.4)", async () => {
    const evidence = { sql: "SELECT vence, multa FROM x", rows: [{ vence: "2026-10-01", multa: "12.50", nota: null }] }
    render(<AnswerView result={{ ...base, evidence }} />)
    await userEvent.click(screen.getByText("Ver evidencia"))
    expect(await screen.findByText("SELECT vence, multa FROM x")).toBeInTheDocument()
    expect(screen.getByText("2026-10-01")).toBeInTheDocument()
    expect(screen.getByText("12.50")).toBeInTheDocument()
    expect(screen.getByText("NULL")).toBeInTheDocument()
  })

  it("evidencia documental: documento y ubicación de cada fragmento (R-8.4)", async () => {
    const evidence = { chunks: [{ document: "reglamento.pdf", location: "p. 4", text: "El préstamo dura 14 días." }] }
    render(<AnswerView result={{ ...base, classification: "rag", sources: ["RAG"], evidence }} />)
    await userEvent.click(screen.getByText("Ver evidencia"))
    expect(await screen.findByText("reglamento.pdf · p. 4")).toBeInTheDocument()
    expect(screen.getByText("El préstamo dura 14 días.")).toBeInTheDocument()
  })

  describe("respuesta como Markdown (R-8.11)", () => {
    it("lista con negritas, sin asteriscos visibles", () => {
      render(<AnswerView result={{ ...base, answer: "Libros:\n\n*   **Clean Code**\n*   **Alas de sangre**" }} />)
      expect(screen.getAllByRole("listitem")).toHaveLength(2)
      expect(screen.getByText("Clean Code").tagName).toBe("STRONG")
      expect(document.body.textContent).not.toContain("*")
    })

    it("tabla GFM con el componente Table", () => {
      render(<AnswerView result={{ ...base, answer: "| Editorial | Libro |\n| --- | --- |\n| Planeta | Alas de hierro |" }} />)
      expect(screen.getByRole("table")).toHaveAttribute("data-slot", "table")
      expect(screen.getByRole("columnheader", { name: "Editorial" })).toBeInTheDocument()
      expect(screen.getByRole("cell", { name: "Alas de hierro" })).toBeInTheDocument()
    })

    it("no interpreta HTML de la respuesta", () => {
      const { container } = render(<AnswerView result={{ ...base, answer: "Hola <img src=x onerror=alert(1)> <script>x</script>" }} />)
      expect(container.querySelector("img, script")).toBeNull()
    })

    it("texto plano con saltos de línea queda completo", () => {
      render(<AnswerView result={{ ...base, answer: "Primera línea\nSegunda línea" }} />)
      expect(document.querySelector("br")).not.toBeNull()
      expect(screen.getByText(/Primera línea/)).toBeInTheDocument()
      expect(screen.getByText(/Segunda línea/)).toBeInTheDocument()
    })

    it("abre los enlaces en otra pestaña", () => {
      render(<AnswerView result={{ ...base, answer: "[doc](https://example.com)" }} />)
      expect(screen.getByRole("link", { name: "doc" })).toHaveAttribute("target", "_blank")
    })

    it("no_coverage y error siguen en Alert, sin formato", () => {
      render(<AnswerView result={{ ...base, answer_kind: "no_coverage", answer: "**No** hay datos." }} />)
      expect(screen.getByText("**No** hay datos.")).toBeInTheDocument()
    })
  })
})
