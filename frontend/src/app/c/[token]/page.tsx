import { AppLink } from "@/lib/site-context"
import { Logo } from "@/components/brand/Logo"
import { Button } from "@/components/ui/button"

/** The retired analysis share link (four-doors spec, decision 43). Counselors
 *  still hold old links, so a notice rather than a 404 that looks like a bug. */
export default function LienConseillerRetirePage() {
  return (
    <div className="bg-mesh flex min-h-screen items-center justify-center px-5 py-12">
      <div className="w-full max-w-md text-center">
        <Logo className="mx-auto text-2xl" />
        <h1 className="mt-10 font-display text-2xl font-bold text-navy">Ce lien n’est plus actif.</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Les conseillers reçoivent désormais l’analyse complète dans leur espace, lorsque leur code est utilisé.
        </p>
        <Button render={<AppLink href="/" />} variant="outline" size="lg" className="mt-6">
          Retour à l’accueil
        </Button>
      </div>
    </div>
  )
}
