"use client"

import { useEffect, useState } from "react"
import { Mail } from "lucide-react"
import { api, apiHref } from "@/lib/api"
import { cn } from "@/lib/utils"
import { Button, buttonVariants } from "@/components/ui/button"
import { Separator } from "@/components/ui/separator"
import { EmailLinkForm } from "@/components/auth/EmailLinkForm"
import { GoogleLogo, MicrosoftLogo } from "@/components/auth/ProviderLogos"

type Providers = { google: boolean; microsoft: boolean }

const PROVIDERS = [
  { id: "google", label: "Continuer avec Google", Logo: GoogleLogo },
  { id: "microsoft", label: "Continuer avec Microsoft", Logo: MicrosoftLogo },
] as const

interface Props {
  /** The page's ?redirect=, already checked by safeRedirect. */
  next: string | null
  /** Under the options: « ou » on /connexion, « ou avec un mot de passe » on /inscription. */
  separator: string
}

/** The password-less ways in (social sign-in spec). A provider button is a
 *  plain link to the server, which runs the whole OAuth round trip — no
 *  provider script ever loads here. It shows only once the server says
 *  that provider's keys are set. */
export function SocialSignIn({ next, separator }: Props) {
  const [providers, setProviders] = useState<Providers>({ google: false, microsoft: false })
  const [linkOpen, setLinkOpen] = useState(false)

  useEffect(() => {
    let live = true
    api.get<Providers>("/auth/providers", { skipRedirect: true })
      .then((p) => { if (live) setProviders(p) })
      // No provider buttons then: the email link and the password still work.
      .catch(() => {})
    return () => { live = false }
  }, [])

  const startHref = (id: string) =>
    apiHref(`/auth/${id}/start${next ? `?next=${encodeURIComponent(next)}` : ""}`)

  return (
    <div className="mt-7">
      <div className="space-y-2.5">
        {PROVIDERS.filter((p) => providers[p.id]).map(({ id, label, Logo }) => (
          <a
            key={id}
            href={startHref(id)}
            className={cn(buttonVariants({ variant: "outline" }), "h-11 w-full gap-2.5 text-[0.95rem]")}
          >
            <Logo className="size-5" /> {label}
          </a>
        ))}
        {linkOpen ? (
          <EmailLinkForm next={next} />
        ) : (
          <Button
            type="button"
            variant="outline"
            className="h-11 w-full gap-2.5 text-[0.95rem]"
            onClick={() => setLinkOpen(true)}
          >
            <Mail className="size-5" /> Recevoir un lien de connexion
          </Button>
        )}
      </div>
      <div className="my-6 flex items-center gap-3 text-xs text-muted-foreground">
        <Separator className="flex-1" />
        <span>{separator}</span>
        <Separator className="flex-1" />
      </div>
    </div>
  )
}
