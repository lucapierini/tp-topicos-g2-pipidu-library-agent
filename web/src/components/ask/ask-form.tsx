import { useState, type FormEvent, type KeyboardEvent } from "react"
import { ArrowUp02Icon, StopCircleIcon } from "@hugeicons/core-free-icons"
import { HugeiconsIcon } from "@hugeicons/react"
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field"
import { InputGroup, InputGroupAddon, InputGroupButton, InputGroupTextarea } from "@/components/ui/input-group"

export function AskForm({
  running,
  onSubmit,
  onCancel,
  initialValue = "",
}: {
  running: boolean
  onSubmit: (question: string) => void
  onCancel: () => void
  initialValue?: string
}) {
  const [text, setText] = useState(initialValue)
  const empty = text.trim() === ""

  function submit(event?: FormEvent) {
    event?.preventDefault()
    if (running || empty) return
    onSubmit(text.trim())
    setText("")
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault()
      submit()
    }
  }

  return (
    <form onSubmit={submit} className="w-full">
      <FieldGroup>
        <Field>
          <FieldLabel htmlFor="question" className="sr-only">
            Consulta
          </FieldLabel>
          <InputGroup>
            <InputGroupTextarea
              id="question"
              placeholder="Preguntá sobre libros, préstamos o el reglamento…"
              value={text}
              onChange={(event) => setText(event.target.value)}
              onKeyDown={onKeyDown}
              readOnly={running}
              className="min-h-16"
            />
            <InputGroupAddon align="block-end">
              {running ? (
                <InputGroupButton size="icon-sm" variant="default" className="ml-auto" onClick={onCancel}>
                  <HugeiconsIcon icon={StopCircleIcon} />
                  <span className="sr-only">Cancelar</span>
                </InputGroupButton>
              ) : (
                <InputGroupButton size="icon-sm" variant="default" type="submit" disabled={empty} className="ml-auto">
                  <HugeiconsIcon icon={ArrowUp02Icon} />
                  <span className="sr-only">Enviar</span>
                </InputGroupButton>
              )}
            </InputGroupAddon>
          </InputGroup>
        </Field>
      </FieldGroup>
    </form>
  )
}
