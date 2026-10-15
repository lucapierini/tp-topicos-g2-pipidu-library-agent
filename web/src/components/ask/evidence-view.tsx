import { ArrowDown01Icon } from "@hugeicons/core-free-icons"
import { HugeiconsIcon } from "@hugeicons/react"
import { Button } from "@/components/ui/button"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import { Separator } from "@/components/ui/separator"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import type { SqlEvidence } from "@/lib/ask-stream"

/** Los valores se muestran tal como llegan, sin reinterpretarlos (R-8.4). */
function cell(value: unknown): string {
  if (value === null) return "NULL"
  return typeof value === "object" ? JSON.stringify(value) : String(value)
}

export function hasEvidence(evidence: SqlEvidence | undefined): boolean {
  return Boolean(evidence?.sql || evidence?.rows?.length || evidence?.chunks?.length)
}

export function EvidenceView({ evidence }: { evidence: SqlEvidence | undefined }) {
  if (!evidence || !hasEvidence(evidence)) return null
  const rows = evidence.rows ?? []
  const columns = rows.length ? Object.keys(rows[0]) : []
  return (
    <Collapsible className="flex flex-col gap-2">
      <CollapsibleTrigger render={<Button variant="outline" size="sm" className="w-fit" />}>
        Ver evidencia
        <HugeiconsIcon icon={ArrowDown01Icon} data-icon="inline-end" />
      </CollapsibleTrigger>
      <CollapsibleContent className="flex flex-col gap-4">
        {evidence.sql ? (
          <div className="flex flex-col gap-2">
            <p className="text-xs font-medium text-muted-foreground">Sentencia SQL ejecutada</p>
            <pre className="overflow-x-auto rounded-xl bg-muted p-3 font-mono text-xs">{evidence.sql}</pre>
          </div>
        ) : null}
        {rows.length ? (
          <div className="flex flex-col gap-2">
            <p className="text-xs font-medium text-muted-foreground">Filas ({rows.length})</p>
            <Table>
              <TableHeader>
                <TableRow>
                  {columns.map((column) => (
                    <TableHead key={column}>{column}</TableHead>
                  ))}
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((row, index) => (
                  <TableRow key={index}>
                    {columns.map((column) => (
                      <TableCell key={column}>{cell(row[column])}</TableCell>
                    ))}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        ) : null}
        {evidence.chunks?.length ? (
          <div className="flex flex-col gap-3">
            <p className="text-xs font-medium text-muted-foreground">Fragmentos citados</p>
            {evidence.chunks.map((chunk, index) => (
              <div key={index} className="flex flex-col gap-1">
                {index > 0 ? <Separator /> : null}
                <p className="text-xs font-medium">
                  {chunk.document} · {chunk.location}
                </p>
                {chunk.text ? <p className="text-sm text-muted-foreground">{chunk.text}</p> : null}
              </div>
            ))}
          </div>
        ) : null}
      </CollapsibleContent>
    </Collapsible>
  )
}
