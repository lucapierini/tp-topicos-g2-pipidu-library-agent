import type { ReactNode } from "react"
import { cn } from "cn"
import type { AskEvent } from "@/lib/ask-stream"
import { describeEvent } from "@/lib/progress"

type StepStatus = "done" | "failed" | "active"

/** Línea de tiempo vertical: punto por paso y una línea que los une. El último paso es el que está en curso. */
function Step({ status, last, children }: { status: StepStatus; last: boolean; children: ReactNode }) {
  return (
    <li className="relative flex gap-3 pb-4 last:pb-0" data-status={status} aria-current={status === "active" ? "step" : undefined}>
      <div className="relative flex w-4 shrink-0 justify-center pt-1.5">
        <span
          aria-hidden="true"
          className={cn(
            "z-10 size-2 rounded-full",
            status === "done" && "bg-muted-foreground/60",
            status === "failed" && "bg-destructive",
            status === "active" && "bg-primary ring-4 ring-primary/20 motion-safe:animate-pulse"
          )}
        />
        {!last && <span aria-hidden="true" className="absolute top-3.5 -bottom-[1.625rem] w-px bg-border" />}
      </div>
      <div
        className={cn(
          "min-w-0 text-sm wrap-break-word",
          status === "done" && "text-muted-foreground",
          status === "failed" && "text-destructive",
          status === "active" && "text-foreground"
        )}
      >
        {children}
      </div>
    </li>
  )
}

export function ProgressPanel({ progress, elapsed }: { progress: AskEvent[]; elapsed: number }) {
  const steps = progress
    .map((event) => ({ text: describeEvent(event), failed: event.type === "tool_result" && !event.ok }))
    .filter((step): step is { text: string; failed: boolean } => step.text !== null)
  return (
    <ol className="flex flex-col" aria-label="Progreso de la consulta" aria-live="polite">
      {steps.map((step, index) => (
        <Step key={index} status={step.failed ? "failed" : "done"} last={false}>
          {step.text}
        </Step>
      ))}
      <Step status="active" last>
        <span className="shimmer inline-block" role="status">{elapsed > 0 ? `Trabajando… ${elapsed} s` : "Trabajando…"}</span>
      </Step>
    </ol>
  )
}
