export const metadata = { title: "neoori — Politique de confidentialité" }

// RGPD privacy policy skeleton. [À COMPLÉTER] fields and a legal/DPO review
// are required before production.
export default function ConfidentialitePage() {
  return (
    <article>
      <h1>Politique de confidentialité</h1>
      <p>Dernière mise à jour : [À COMPLÉTER : date]</p>

      <h2>1. Responsable de traitement</h2>
      <p>
        [À COMPLÉTER : dénomination de l&apos;éditeur], contact : [À COMPLÉTER : email RGPD].
      </p>

      <h2>2. Données collectées</h2>
      <ul>
        <li><strong>Compte</strong> : adresse email, mot de passe (haché).</li>
        <li>
          <strong>Analyse de CV</strong> : contenu du CV, projet visé, prénom, nom, tranche
          d&apos;âge, localisation, situation actuelle, type de mobilité, notes éventuelles
          (pouvant inclure des informations sensibles que vous choisissez de communiquer, par
          exemple une RQTH).
        </li>
        <li><strong>Paiement</strong> : traité par Stripe ; neoori ne voit jamais votre carte.</li>
      </ul>

      <h2>3. Finalités et bases légales</h2>
      <ul>
        <li>Génération du rapport d&apos;analyse — exécution du contrat.</li>
        <li>Gestion du compte et des paiements — exécution du contrat / obligation légale.</li>
        <li>Amélioration du service (statistiques d&apos;usage agrégées) — intérêt légitime.</li>
      </ul>

      <h2>4. Traitement par intelligence artificielle</h2>
      <p>
        Le contenu de votre CV et vos réponses sont transmis à Anthropic (Claude), notre
        sous-traitant d&apos;inférence, pour générer le rapport. Conformément à la politique
        commerciale d&apos;Anthropic, ces données ne sont pas utilisées pour entraîner ses modèles.
        Le rapport généré et la réponse brute sont conservés afin de vous restituer votre analyse.
      </p>

      <h2>5. Destinataires et sous-traitants</h2>
      <ul>
        <li>Vercel (hébergement frontend, États-Unis — clauses contractuelles types)</li>
        <li>Render (hébergement backend, États-Unis — clauses contractuelles types)</li>
        <li>PingCAP / TiDB Cloud (base de données, AWS région UE)</li>
        <li>Anthropic (génération IA, États-Unis — clauses contractuelles types)</li>
        <li>Stripe (paiement)</li>
      </ul>
      <p>
        Le lien de partage conseiller (« /c/… ») donne accès à une synthèse de votre analyse à
        toute personne disposant du lien : ne le transmettez qu&apos;à votre conseiller.
      </p>

      <h2>6. Durées de conservation</h2>
      <p>
        Vos analyses sont conservées tant que votre compte est actif. Vous pouvez supprimer chaque
        analyse à tout moment depuis votre espace ; la suppression est immédiate et définitive.
        [À COMPLÉTER : durée de conservation des comptes inactifs, ex. 2 ans.]
      </p>

      <h2>7. Vos droits</h2>
      <p>
        Vous disposez des droits d&apos;accès, de rectification, d&apos;effacement, de limitation,
        d&apos;opposition et de portabilité (art. 15 à 22 RGPD). Exercez-les auprès de
        [À COMPLÉTER : email RGPD]. Vous pouvez saisir la CNIL (<a href="https://www.cnil.fr" target="_blank" rel="noopener noreferrer">cnil.fr</a>) à tout moment.
      </p>

      <h2>8. Cookies</h2>
      <p>
        neoori utilise uniquement des cookies strictement nécessaires à l&apos;authentification
        (jetons de session). Aucun cookie publicitaire ou de mesure d&apos;audience tierce n&apos;est
        déposé — aucun bandeau de consentement n&apos;est donc requis.
      </p>
    </article>
  )
}
