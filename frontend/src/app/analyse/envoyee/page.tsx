import { AppLink } from "@/lib/site-context"
import { CheckCircle2 } from "lucide-react"
import { Logo } from "@/components/brand/Logo"
import { Button } from "@/components/ui/button"

/** After the advisor door (four-doors spec, decision 26): no link, no id, no
 *  content — the report is the counselor's. */
export default function AnalyseEnvoyeePage() {
  return (
    <div className="bg-mesh flex min-h-screen items-center justify-center px-5 py-12">
      <div className="w-full max-w-md text-center">
        <Logo className="mx-auto text-2xl" />
        <CheckCircle2 className="mx-auto mt-10 size-8 text-success" />
        <h1 className="mt-4 font-display text-2xl font-bold text-navy">C’est envoyé.</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Votre conseiller recevra votre analyse d’ici quelques minutes, dans son espace. Il pourra vous la présenter lors de votre prochain échange.
        </p>
        <Button render={<AppLink href="/" />} variant="outline" size="lg" className="mt-6">
          Retour à l’accueil
        </Button>
      </div>
    </div>
  )
}
