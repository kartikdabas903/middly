import { ArrowRight, Building2, ShieldCheck } from "lucide-react"
import Link from "next/link"

import { buttonVariants } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { CATEGORY_INFO } from "@/lib/format"
import type { ServiceInfo } from "@/lib/types"
import { cn } from "@/lib/utils"

export function ServiceCard({ service }: { service: ServiceInfo }) {
  return (
    <Card className="h-full" data-testid={`service-${service.code}`}>
      <CardHeader>
        <div className="flex items-start justify-between gap-2">
          <CardTitle className="text-lg">{service.name}</CardTitle>
        </div>
        <CardDescription className="flex items-center gap-1.5">
          <Building2 className="size-3.5" /> {service.department}
        </CardDescription>
      </CardHeader>
      <CardContent className="flex-1 space-y-3 text-sm">
        <p className="text-muted-foreground">{service.description}</p>
        {service.required_categories.length > 0 && (
          <div>
            <p className="mb-1.5 flex items-center gap-1.5 text-xs font-semibold text-foreground">
              <ShieldCheck className="size-3.5 text-primary" /> Fetched with your consent — no uploads
            </p>
            <div className="flex flex-wrap gap-1.5">
              {service.required_categories.map((c) => (
                <span key={c} className="rounded-full bg-secondary px-2 py-0.5 text-xs text-secondary-foreground">
                  {CATEGORY_INFO[c]?.label ?? c} · {CATEGORY_INFO[c]?.source}
                </span>
              ))}
            </div>
          </div>
        )}
        {service.eligibility && (
          <div className="rounded-lg border border-dashed p-2.5">
            <p className="text-xs font-semibold">Eligibility</p>
            <ul className="mt-1 list-inside list-disc text-xs text-muted-foreground">
              {service.eligibility.rules.map((r) => (
                <li key={r.id}>{r.description}</li>
              ))}
            </ul>
          </div>
        )}
      </CardContent>
      <CardFooter>
        <Link href={`/citizen/apply/${service.code}`} className={cn(buttonVariants({ size: "lg" }), "w-full")} data-testid={`apply-${service.code}`}>
          {service.code === "GRIEVANCE_REDRESSAL" ? "Raise a grievance" : "Apply now"} <ArrowRight className="size-4" />
        </Link>
      </CardFooter>
    </Card>
  )
}
