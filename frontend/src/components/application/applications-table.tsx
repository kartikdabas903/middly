"use client"

import { ChevronRight } from "lucide-react"
import Link from "next/link"

import { StatusBadge } from "@/components/common/status"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { formatDate, timeAgo } from "@/lib/format"
import type { ApplicationSummary } from "@/lib/types"

export function ApplicationsTable({
  items,
  hrefBase,
  showApplicant = false,
}: {
  items: ApplicationSummary[]
  hrefBase: string
  showApplicant?: boolean
}) {
  return (
    <div className="overflow-hidden rounded-xl border bg-white">
      <Table data-testid="applications-table">
        <TableHeader>
          <TableRow className="bg-muted/50">
            <TableHead>Application ID</TableHead>
            {showApplicant && <TableHead>Applicant</TableHead>}
            <TableHead>Department / Service</TableHead>
            <TableHead>Current status</TableHead>
            <TableHead className="hidden lg:table-cell">Workflow step</TableHead>
            <TableHead className="hidden md:table-cell">Submitted</TableHead>
            <TableHead className="hidden md:table-cell">Last updated</TableHead>
            <TableHead className="hidden xl:table-cell">Expected next action</TableHead>
            <TableHead className="w-8" />
          </TableRow>
        </TableHeader>
        <TableBody>
          {items.map((a) => (
            <TableRow key={a.id} className="group cursor-pointer" data-app={a.application_number}>
              <TableCell className="font-mono text-sm font-semibold">
                <Link href={`${hrefBase}/${a.id}`} className="text-primary hover:underline">
                  {a.application_number}
                </Link>
              </TableCell>
              {showApplicant && (
                <TableCell>
                  <span className="block font-medium">{a.applicant_name ?? "—"}</span>
                  <span className="block text-xs text-muted-foreground">ID {a.citizen_id}</span>
                </TableCell>
              )}
              <TableCell className="max-w-56">
                <span className="block truncate font-medium">{a.department}</span>
                <span className="block truncate text-xs text-muted-foreground">{a.service}</span>
              </TableCell>
              <TableCell>
                <StatusBadge status={a.status} />
              </TableCell>
              <TableCell className="hidden text-sm lg:table-cell">{a.current_step_label ?? "—"}</TableCell>
              <TableCell className="hidden text-sm whitespace-nowrap md:table-cell">{formatDate(a.submitted_at)}</TableCell>
              <TableCell className="hidden text-sm whitespace-nowrap text-muted-foreground md:table-cell">{timeAgo(a.updated_at)}</TableCell>
              <TableCell className="hidden max-w-64 text-xs text-muted-foreground xl:table-cell">{a.expected_next_action}</TableCell>
              <TableCell>
                <Link href={`${hrefBase}/${a.id}`} aria-label={`Open ${a.application_number}`}>
                  <ChevronRight className="size-4 text-muted-foreground group-hover:text-primary" />
                </Link>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}
