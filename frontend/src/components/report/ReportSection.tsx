import Link from "next/link"
import ReactMarkdown from "react-markdown"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import { Separator } from "@/components/ui/separator"
import { Lock } from "lucide-react"
import { cn } from "@/lib/utils"
import { reportMarkdown } from "./markdown"

type SectionItem = string | { fact?: string }
export type SectionData = { title?: string; body_markdown?: string; items?: SectionItem[] }

const itemText = (it: SectionItem) => (typeof it === "string" ? it : it.fact ?? String(it))

function toMarkdown(section: SectionData): string {
  return (
    section.body_markdown ||
    (section.items?.length ? section.items.map((it) => `- ${itemText(it)}`).join("\n") : "")
  )
}

function TagCloud({ section }: { section: SectionData }) {
  const tags = section.items?.length
    ? section.items.map(itemText)
    : (section.body_markdown ?? "").split(/[·\n,]/).map((t) => t.trim()).filter(Boolean)
  return (
    <div className="mt-1 grid grid-cols-2 gap-1.5 sm:grid-cols-3">
      {tags.map((t, i) => (
        <span key={i} className="rounded-md bg-secondary px-2.5 py-1.5 text-center text-xs font-medium text-navy">
          {t}
        </span>
      ))}
    </div>
  )
}

/** One analysis section: §n band + title, with locked / tag-cloud / markdown / loading states. */
export function ReportSection({
  n,
  title,
  section,
  locked = false,
  paid = false,
  counselor = false,
  unlockHref,
}: {
  n: string
  title: string
  section?: SectionData
  locked?: boolean
  paid?: boolean
  counselor?: boolean
  unlockHref?: string
}) {
  return (
    <div className={cn("print-break mb-7", locked && "opacity-60")}>
      <div className="mb-3 flex items-stretch overflow-hidden rounded-md">
        <span className="flex w-9 shrink-0 items-center justify-center bg-orange-dark font-mono text-[11px] font-bold text-white">
          §{n}
        </span>
        <div className="flex flex-1 items-center gap-2 bg-navy px-3 py-2">
          <h2 className="font-display text-sm font-bold uppercase leading-tight tracking-wide text-white">{title}</h2>
          {paid && !counselor && <Badge variant="peach" className="ml-auto shrink-0 text-[10px]">plan payant</Badge>}
        </div>
      </div>

      {locked ? (
        <div className="flex items-center gap-2 py-4 text-muted-foreground" aria-label="Section verrouillée">
          <Lock className="size-4" aria-hidden="true" />
          <span className="text-sm">
            Disponible avec le plan complet.
            {unlockHref && (
              <>
                {" "}
                <Link href={unlockHref} className="text-primary underline">Débloquer →</Link>
              </>
            )}
          </span>
        </div>
      ) : section ? (
        <div className="text-sm leading-relaxed text-foreground/90">
          {n === "3" ? <TagCloud section={section} /> : <ReactMarkdown components={reportMarkdown}>{toMarkdown(section)}</ReactMarkdown>}
        </div>
      ) : (
        <div className="space-y-2">
          <Skeleton className="h-3 w-full" />
          <Skeleton className="h-3 w-4/5" />
          <Skeleton className="h-3 w-3/5" />
        </div>
      )}

      <Separator className="mt-6" />
    </div>
  )
}
