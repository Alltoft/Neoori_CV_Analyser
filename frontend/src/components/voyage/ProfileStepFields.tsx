"use client"

import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select"
import type { ProfileStep } from "@/lib/profile-steps"

/**
 * The plain fields of one profile step.
 *
 * Controlled from the outside and deliberately free of react-hook-form: two
 * surfaces render these — the hub's consent gate inlines « entrée », the step
 * page serves « parcours » — and a component that owns its own form state
 * could only be used by one of them.
 *
 * Required fields carry no asterisk: the submit button says what is missing,
 * and a form of three questions does not need decoration to be read.
 */
export function ProfileStepFields({
  step,
  values,
  onChange,
  disabled,
}: {
  step: ProfileStep
  values: Record<string, string>
  onChange: (name: string, value: string) => void
  disabled?: boolean
}) {
  return (
    <div className="space-y-4">
      {step.fields.map((field) => {
        const id = `step-${step.key}-${field.name}`
        const value = values[field.name] ?? ""

        return (
          <div key={field.name} className="space-y-1.5">
            <Label htmlFor={id}>{field.label}</Label>

            {field.kind === "select" ? (
              <Select
                value={value}
                onValueChange={(next) => onChange(field.name, next ?? "")}
                disabled={disabled}
              >
                <SelectTrigger id={id} className="h-10 w-full">
                  <SelectValue placeholder="Choisir…" />
                </SelectTrigger>
                <SelectContent>
                  {(field.options ?? []).map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            ) : field.kind === "textarea" ? (
              <Textarea
                id={id}
                rows={3}
                placeholder={field.placeholder}
                value={value}
                disabled={disabled}
                onChange={(e) => onChange(field.name, e.target.value)}
              />
            ) : (
              <Input
                id={id}
                className="h-10"
                placeholder={field.placeholder}
                value={value}
                disabled={disabled}
                onChange={(e) => onChange(field.name, e.target.value)}
              />
            )}

            {field.hint && (
              <p className="text-xs leading-relaxed text-muted-foreground">{field.hint}</p>
            )}
          </div>
        )
      })}
    </div>
  )
}
