"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { FlaskConical, PlayCircle, RotateCcw } from "lucide-react"
import { useState } from "react"
import { toast } from "sonner"

import { Spinner } from "@/components/common/page"
import { StatusBadge } from "@/components/common/status"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import { api, errorMessage } from "@/lib/api"
import type { ConnectorCard } from "@/lib/types"
import { cn } from "@/lib/utils"

const MODES = [
  { mode: "HEALTHY", label: "Healthy" },
  { mode: "DEGRADED", label: "Degraded" },
  { mode: "DOWN", label: "Down" },
] as const

export function FaultButtons({ connector }: { connector: ConnectorCard }) {
  const qc = useQueryClient()
  const fault = useMutation({
    mutationFn: (mode: string) => api.post(`demo/connectors/${connector.key}/fault`, { mode }),
    onSuccess: (_, mode) => {
      toast.success(`${connector.system_name} set to ${mode}`)
      qc.invalidateQueries({ queryKey: ["connectors"] })
      qc.invalidateQueries({ queryKey: ["admin", "overview"] })
    },
    onError: (e) => toast.error(errorMessage(e)),
  })
  const current = connector.fault_mode ?? "HEALTHY"
  return (
    <div className="flex flex-wrap items-center gap-1" role="group" aria-label={`Simulated state for ${connector.system_name}`}>
      {MODES.map((m) => (
        <Button
          key={m.mode}
          size="xs"
          variant={current === m.mode ? "default" : "outline"}
          className={cn(current === m.mode && m.mode === "DOWN" && "bg-red-600 hover:bg-red-600/90", current === m.mode && m.mode === "DEGRADED" && "bg-amber-600 hover:bg-amber-600/90")}
          disabled={fault.isPending}
          onClick={() => fault.mutate(m.mode)}
          data-testid={`fault-${connector.key}-${m.mode}`}
        >
          {m.label}
        </Button>
      ))}
      {fault.isPending && <Spinner className="ml-1" />}
    </div>
  )
}

interface Scenario {
  id: number
  title: string
  persona: string
  steps: string[]
}

export function DemoScenarios({ connectors, canControl }: { connectors: ConnectorCard[]; canControl: boolean }) {
  const qc = useQueryClient()
  const { data } = useQuery({ queryKey: ["demo", "scenarios"], queryFn: () => api.get<{ demo_mode: boolean; scenarios: Scenario[] }>("demo/scenarios"), enabled: canControl })
  const [confirm, setConfirm] = useState(false)
  const reset = useMutation({
    mutationFn: () => api.post("demo/reset"),
    onSuccess: () => {
      toast.success("Sandbox reset — sample data re-created")
      setConfirm(false)
      qc.invalidateQueries()
    },
    onError: (e) => toast.error(errorMessage(e)),
  })
  const scenarios = data?.scenarios ?? []

  return (
    <Card data-testid="demo-scenarios">
      <CardHeader>
        <CardTitle className="flex flex-wrap items-center gap-2">
          <FlaskConical className="size-4 text-muted-foreground" /> Walkthrough scenarios
          {canControl && (
            <Dialog open={confirm} onOpenChange={setConfirm}>
              <DialogTrigger render={<Button variant="outline" size="sm" className="ml-auto" />}>
                <RotateCcw className="size-3.5" /> Reset sandbox data
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Reset the sandbox?</DialogTitle>
                  <DialogDescription>
                    All platform data is wiped, the sample department systems are reset and the sample data is re-created (same as npm run reset;
                    takes about 10 seconds).
                  </DialogDescription>
                </DialogHeader>
                <DialogFooter>
                  <Button variant="destructive" onClick={() => reset.mutate()} disabled={reset.isPending}>
                    {reset.isPending && <Spinner />} Reset &amp; re-seed
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          )}
        </CardTitle>
        <CardDescription>Step-by-step walkthroughs of the main flows. Outage simulation only affects the sample department systems in this environment.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-5">
        <div className="grid gap-4 lg:grid-cols-3">
          {scenarios.map((s) => (
            <div key={s.id} className="rounded-xl border bg-white p-4">
              <p className="flex items-center gap-2 font-semibold">
                <PlayCircle className="size-4 text-primary" /> Scenario {s.id}: {s.title}
              </p>
              <p className="mt-0.5 text-xs text-muted-foreground">{s.persona}</p>
              <ol className="mt-3 list-decimal space-y-1 pl-4 text-xs text-foreground/80">
                {s.steps.map((step, i) => (
                  <li key={i}>{step}</li>
                ))}
              </ol>
            </div>
          ))}
          {!canControl && <p className="text-sm text-muted-foreground">Sandbox tools are available to platform administrators.</p>}
        </div>
        {canControl && (
          <div>
            <p className="mb-2 text-sm font-semibold">Simulate department outages</p>
            <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
              {connectors.map((c) => (
                <div key={c.key} className="flex items-center justify-between gap-2 rounded-lg border bg-white p-2.5">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium">{c.system_name}</p>
                    <StatusBadge status={c.status} />
                  </div>
                  <FaultButtons connector={c} />
                </div>
              ))}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
