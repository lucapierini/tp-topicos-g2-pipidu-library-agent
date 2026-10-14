import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"
import { AskForm } from "./ask-form"

describe("AskForm", () => {
  it("no envía una consulta vacía o de solo espacios (R-8.1)", async () => {
    const onSubmit = vi.fn()
    render(<AskForm running={false} onSubmit={onSubmit} onCancel={() => {}} />)
    const send = screen.getByRole("button", { name: "Enviar" })
    expect(send).toBeDisabled()
    await userEvent.type(screen.getByLabelText("Consulta"), "   {Enter}")
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it("envía el texto recortado con Enter y con el botón", async () => {
    const onSubmit = vi.fn()
    render(<AskForm running={false} onSubmit={onSubmit} onCancel={() => {}} />)
    await userEvent.type(screen.getByLabelText("Consulta"), " hola {Enter}")
    expect(onSubmit).toHaveBeenCalledWith("hola")
    expect(screen.getByLabelText("Consulta")).toHaveValue("") // se limpia al enviar
    await userEvent.type(screen.getByLabelText("Consulta"), "chau")
    await userEvent.click(screen.getByRole("button", { name: "Enviar" }))
    expect(onSubmit).toHaveBeenLastCalledWith("chau")
  })

  it("mientras corre no permite enviar y ofrece cancelar (R-8.1, R-8.5)", async () => {
    const onSubmit = vi.fn()
    const onCancel = vi.fn()
    render(<AskForm running onSubmit={onSubmit} onCancel={onCancel} initialValue="algo" />)
    expect(screen.queryByRole("button", { name: "Enviar" })).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole("button", { name: "Cancelar" }))
    expect(onCancel).toHaveBeenCalled()
    expect(onSubmit).not.toHaveBeenCalled()
  })
})
