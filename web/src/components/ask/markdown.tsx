import type { ComponentProps } from "react"
import ReactMarkdown, { type Components } from "react-markdown"
import remarkBreaks from "remark-breaks"
import remarkGfm from "remark-gfm"
import { Separator } from "@/components/ui/separator"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { cn } from "@/lib/utils"

/** Sin `rehype-raw`: el HTML dentro de la respuesta no se interpreta (R-8.11). */
const components: Components = {
  p: (props) => <p className="leading-relaxed" {...props} />,
  ul: (props) => <ul className="flex list-disc flex-col gap-1 pl-5" {...props} />,
  ol: (props) => <ol className="flex list-decimal flex-col gap-1 pl-5" {...props} />,
  h1: (props) => <h3 className="text-base font-semibold" {...props} />,
  h2: (props) => <h3 className="text-base font-semibold" {...props} />,
  h3: (props) => <h4 className="text-sm font-semibold" {...props} />,
  h4: (props) => <h4 className="text-sm font-semibold" {...props} />,
  a: (props) => <a className="underline underline-offset-4" target="_blank" rel="noreferrer noopener" {...props} />,
  blockquote: (props) => <blockquote className="border-l-2 pl-3 text-muted-foreground" {...props} />,
  hr: () => <Separator />,
  pre: (props) => <pre className="overflow-x-auto rounded-xl bg-muted p-3 font-mono text-xs" {...props} />,
  code: ({ className, ...props }: ComponentProps<"code">) => (
    <code className={cn("rounded bg-muted px-1 py-0.5 font-mono text-[0.85em] [pre_&]:bg-transparent [pre_&]:p-0", className)} {...props} />
  ),
  table: (props) => <Table {...props} />,
  thead: (props) => <TableHeader {...props} />,
  tbody: (props) => <TableBody {...props} />,
  tr: (props) => <TableRow {...props} />,
  th: (props) => <TableHead {...props} />,
  td: (props) => <TableCell className="whitespace-normal" {...props} />,
}

export function Markdown({ children }: { children: string }) {
  return (
    <div className="flex min-w-0 flex-col gap-3">
      <ReactMarkdown remarkPlugins={[remarkGfm, remarkBreaks]} components={components}>
        {children}
      </ReactMarkdown>
    </div>
  )
}
