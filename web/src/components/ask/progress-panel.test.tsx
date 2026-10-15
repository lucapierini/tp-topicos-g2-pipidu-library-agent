import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import type { AskEvent } from "@/lib/ask-stream"
import { ProgressPanel } from "./progress-panel"

describe("ProgressPanel", () => {
  it("muestra clasificación y herramienta sin declarar ninguna fuente (R-8.2)", () => {
    const progress: AskEvent[] = [
      { type: "classified", classification: "sql" },
      { type: "tool_call", tool: "execute_sql", sql: "SELECT 1" },
      { type: "tool_result", tool: "execute_sql", ok: true, rows: 3 },
    ]
    render(<ProgressPanel progress={progress} elapsed={0} />)
    expect(screen.getByText(/Clasificada/)).toBeInTheDocument()
    expect(screen.getByText("Consultando la base de datos")).toBeInTheDocument()
    expect(screen.getByText("Devolvió 3 filas")).toBeInTheDocument()
    expect(screen.queryByText(/Fuente/)).not.toBeInTheDocument()
  })

  it("muestra los segundos de espera del heartbeat", () => {
    render(<ProgressPanel progress={[]} elapsed={15} />)
    expect(screen.getByText("Trabajando… 15 s")).toBeInTheDocument()
  })

  it("indica la espera con shimmer y sin spinner", () => {
    render(<ProgressPanel progress={[]} elapsed={0} />)
    expect(screen.getByText("Trabajando…")).toHaveClass("shimmer")
    expect(document.querySelector('[data-slot="spinner"]')).toBeNull()
  })
})
