import { Marker, MarkerContent, MarkerIcon } from "@/components/ui/marker"
import { Spinner } from "@/components/ui/spinner"
import type { AskEvent } from "@/lib/ask-stream"
import { describeEvent } from "@/lib/progress"

export function ProgressPanel({ progress, elapsed }: { progress: AskEvent[]; elapsed: number }) {
  const lines = progress.map(describeEvent).filter((line): line is string => line !== null)
  return (
    <div className="flex flex-col gap-2" aria-live="polite">
      {lines.map((line, index) => (
        <Marker key={index}>
          <MarkerContent>{line}</MarkerContent>
        </Marker>
      ))}
      <Marker>
        <MarkerIcon>
          <Spinner />
        </MarkerIcon>
        <MarkerContent>{elapsed > 0 ? `Trabajando… ${elapsed} s` : "Trabajando…"}</MarkerContent>
      </Marker>
    </div>
  )
}
