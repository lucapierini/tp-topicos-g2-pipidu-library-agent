import { Alert02Icon } from "@hugeicons/core-free-icons"
import { HugeiconsIcon } from "@hugeicons/react"
import { Alert, AlertAction, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import type { FailureKind } from "@/hooks/use-ask"

const TITLE: Record<FailureKind, string> = {
  unreachable: "No se puede conectar con la API",
  invalid: "La consulta no es válida",
  http: "La API devolvió un error",
  incomplete: "La consulta no se completó",
  agent: "La consulta falló",
}

export function FailureAlert({
  kind,
  message,
  onRetry,
}: {
  kind: FailureKind
  message: string
  onRetry: () => void
}) {
  return (
    <Alert variant="destructive" role="alert">
      <HugeiconsIcon icon={Alert02Icon} />
      <AlertTitle>{TITLE[kind]}</AlertTitle>
      <AlertDescription>{message}</AlertDescription>
      <AlertAction>
        <Button variant="outline" size="sm" onClick={onRetry}>
          Reintentar
        </Button>
      </AlertAction>
    </Alert>
  )
}
