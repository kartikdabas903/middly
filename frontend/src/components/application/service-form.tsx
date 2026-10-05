"use client"

import { zodResolver } from "@hookform/resolvers/zod"
import { Controller, useForm, type Resolver } from "react-hook-form"
import { z } from "zod"

import { Spinner } from "@/components/common/page"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Textarea } from "@/components/ui/textarea"
import type { FormField } from "@/lib/types"

/** Builds a Zod schema from the service's declarative form schema (validated again server-side). */
export function schemaFor(fields: FormField[]) {
  const shape: Record<string, z.ZodType<string>> = {}
  for (const f of fields) {
    if (f.type === "select") {
      const values = (f.options ?? []).map((o) => o.value)
      shape[f.name] = z.string().refine((v) => values.includes(v), { message: `Please choose ${f.label.toLowerCase()}` })
    } else {
      let s = z.string().trim()
      if (f.minLength) s = s.min(f.minLength, `At least ${f.minLength} characters`)
      if (f.maxLength) s = s.max(f.maxLength, `At most ${f.maxLength} characters`)
      shape[f.name] = f.required ? s.min(1, "This field is required") : s
    }
  }
  return z.object(shape)
}

export function ServiceForm({
  fields,
  onSubmit,
  submitting,
  submitLabel,
}: {
  fields: FormField[]
  onSubmit: (values: Record<string, string>) => void
  submitting: boolean
  submitLabel: string
}) {
  const schema = schemaFor(fields)
  const form = useForm<Record<string, string>>({
    resolver: zodResolver(schema) as unknown as Resolver<Record<string, string>>,
    defaultValues: Object.fromEntries(fields.map((f) => [f.name, ""])),
  })

  return (
    <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-5" noValidate data-testid="service-form">
      {fields.map((f) => {
        const err = form.formState.errors[f.name]?.message
        const id = `field-${f.name}`
        return (
          <div key={f.name} className="space-y-1.5">
            <Label htmlFor={id}>
              {f.label}
              {f.required && <span className="text-destructive"> *</span>}
            </Label>
            {f.type === "select" ? (
              <Controller
                control={form.control}
                name={f.name}
                render={({ field }) => (
                  <Select
                    items={(f.options ?? []).map((o) => ({ value: o.value, label: o.label }))}
                    value={field.value || null}
                    onValueChange={(v) => field.onChange(v ?? "")}
                  >
                    <SelectTrigger id={id} className="h-10 w-full" aria-invalid={Boolean(err)} data-testid={id}>
                      <SelectValue placeholder={`Select ${f.label.toLowerCase()}`} />
                    </SelectTrigger>
                    <SelectContent>
                      {(f.options ?? []).map((o) => (
                        <SelectItem key={o.value} value={o.value} data-testid={`option-${o.value}`}>
                          {o.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              />
            ) : f.type === "textarea" ? (
              <Textarea id={id} rows={5} aria-invalid={Boolean(err)} {...form.register(f.name)} data-testid={id} />
            ) : (
              <Input id={id} className="h-10" aria-invalid={Boolean(err)} {...form.register(f.name)} data-testid={id} />
            )}
            {err && (
              <p className="text-xs font-medium text-destructive" role="alert">
                {String(err)}
              </p>
            )}
          </div>
        )
      })}
      <Button type="submit" size="lg" className="h-10 px-5" disabled={submitting} data-testid="submit-application">
        {submitting && <Spinner />} {submitLabel}
      </Button>
    </form>
  )
}
