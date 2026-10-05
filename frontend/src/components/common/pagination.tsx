import { ChevronLeft, ChevronRight } from "lucide-react"

import { Button } from "@/components/ui/button"

export function Pagination({ total, limit, offset, onChange }: { total: number; limit: number; offset: number; onChange: (offset: number) => void }) {
  const page = Math.floor(offset / limit) + 1
  const pages = Math.max(1, Math.ceil(total / limit))
  return (
    <div className="flex items-center justify-between gap-2 py-3 text-sm text-muted-foreground">
      <span>
        {total === 0 ? "No records" : `${offset + 1}–${Math.min(offset + limit, total)} of ${total.toLocaleString("en-IN")}`}
      </span>
      <div className="flex items-center gap-1">
        <Button variant="outline" size="icon-sm" disabled={offset === 0} onClick={() => onChange(Math.max(0, offset - limit))} aria-label="Previous page">
          <ChevronLeft className="size-4" />
        </Button>
        <span className="px-2 tabular-nums">
          {page} / {pages}
        </span>
        <Button variant="outline" size="icon-sm" disabled={offset + limit >= total} onClick={() => onChange(offset + limit)} aria-label="Next page">
          <ChevronRight className="size-4" />
        </Button>
      </div>
    </div>
  )
}
