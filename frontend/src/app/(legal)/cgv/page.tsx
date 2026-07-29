export const metadata = { title: "neoori — Conditions générales de vente" }

// Consumer-law skeleton (Code de la consommation). [À COMPLÉTER] fields and a
// legal review are required before live payments are enabled.
export default function CgvPage() {
  return (
    <article>
      <h1>Conditions générales de vente</h1>
      <p>Dernière mise à jour : [À COMPLÉTER : date de mise en ligne]</p>

      <h2>1. Objet</h2>
      <p>
        Les présentes CGV régissent la vente du service « analyse de CV complète » proposé sur
        neoori par [À COMPLÉTER : dénomination de l&apos;éditeur] (voir mentions légales).
      </p>

      <h2>2. Description du service</h2>
      <p>
        L&apos;offre gratuite comprend les sections 1 à 3 du rapport d&apos;analyse, ainsi qu&apos;un
        verdict de diagnostic. L&apos;offre payante débloque le rapport complet en 9 sections,
        incluant les points à renforcer, les préconisations terrain, un exemple de réécriture,
        la synthèse, les pistes d&apos;évolution et une proposition de CV retravaillé, ainsi que
        l&apos;export conseiller. Le rapport est généré par intelligence artificielle à
        partir des informations fournies par l&apos;utilisateur ; il constitue une aide à la décision
        et non un conseil professionnel individualisé.
      </p>

      <h2>3. Prix</h2>
      <p>
        Le déblocage du rapport complet est proposé au prix de <strong>9 € TTC</strong>, payable en
        une fois, sans abonnement. [À COMPLÉTER si franchise de TVA : « TVA non applicable,
        art. 293 B du CGI. »]
      </p>

      <h2>4. Paiement</h2>
      <p>
        Le paiement s&apos;effectue par carte bancaire via la plateforme sécurisée Stripe. Aucune
        donnée de carte n&apos;est traitée ni conservée par neoori. Le service est délivré
        immédiatement après confirmation du paiement.
      </p>

      <h2>5. Droit de rétractation</h2>
      <p>
        Conformément à l&apos;article L221-28 1° du Code de la consommation, le droit de
        rétractation de 14 jours ne peut être exercé pour un contenu numérique fourni
        immédiatement après l&apos;achat, lorsque le consommateur a expressément consenti à
        l&apos;exécution immédiate et renoncé à son droit de rétractation. Ce consentement est
        recueilli par une case à cocher au moment de l&apos;achat.
      </p>

      <h2>6. Bénéficiaires accompagnés (code conseiller)</h2>
      <p>
        Les bénéficiaires d&apos;un accompagnement Cap Emploi, France Travail, Mission Locale ou CEP
        peuvent obtenir le rapport complet gratuitement au moyen d&apos;un code fourni par leur
        conseiller. Ce code est strictement personnel à la structure qui le délivre.
      </p>

      <h2>7. Réclamations et remboursement</h2>
      <p>
        En cas de défaut de génération du rapport après paiement (erreur technique), l&apos;utilisateur
        est invité à contacter [À COMPLÉTER : email de contact] ; le rapport sera regénéré ou le
        paiement remboursé. Pour toute réclamation, le médiateur de la consommation mentionné dans
        les mentions légales peut être saisi gratuitement.
      </p>

      <h2>8. Droit applicable</h2>
      <p>Les présentes CGV sont soumises au droit français.</p>
    </article>
  )
}
