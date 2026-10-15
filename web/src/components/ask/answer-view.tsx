import { Alert02Icon, InformationCircleIcon } from "@hugeicons/core-free-icons"
import { HugeiconsIcon } from "@hugeicons/react"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Bubble, BubbleContent } from "@/components/ui/bubble"
import type { AgentResult } from "@/lib/ask-stream"
import { EvidenceView } from "./evidence-view"
import { Markdown } from "./markdown"

/** `no_coverage` y `error` no se presentan como una respuesta con fuente (R-8.3). */
export function AnswerView({ result }: { result: AgentResult }) {
  if (result.answer_kind === "no_coverage") {
    return (
      <div className="flex flex-col gap-3">
        <Alert>
          <HugeiconsIcon icon={InformationCircleIcon} />
          <AlertTitle>{result.title ?? "Sin información suficiente"}</AlertTitle>
          <AlertDescription>{result.answer}</AlertDescription>
        </Alert>
      </div>
    )
  }
  if (result.answer_kind === "error") {
    return (
      <Alert variant="destructive">
        <HugeiconsIcon icon={Alert02Icon} />
        <AlertTitle>{result.title ?? "El agente no pudo responder"}</AlertTitle>
        <AlertDescription>{result.answer}</AlertDescription>
      </Alert>
    )
  }
  return (
    <div className="flex flex-col gap-3">
      <Bubble variant="muted" className="max-w-full">
        <BubbleContent>
          <Markdown>{result.answer}</Markdown>
        </BubbleContent>
      </Bubble>
      {result.sources.length ? (
        <div className="flex flex-wrap items-center gap-2" aria-label="Fuentes">
          <span className="text-xs text-muted-foreground">Fuente:</span>
          {result.sources.map((source) => (
            <Badge key={source} variant="secondary">
              {source}
            </Badge>
          ))}
        </div>
      ) : null}
      <EvidenceView evidence={result.evidence} />
    </div>
  )
}
