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
          <strong>Profil de base</strong> : prénom, nom, ville et rayon de recherche, tranche
          d&apos;âge, situation actuelle, projet (et le document qui le décrit, si vous en joignez
          un), contraintes pratiques ; si vous les renseignez, vos conditions de travail et votre
          statut de bénéficiaire de l&apos;obligation d&apos;emploi (voir § 6).
        </li>
        <li>
          <strong>Analyses</strong> : selon le parcours choisi, le contenu de votre CV, la cible
          visée (offre d&apos;emploi ou description) et vos réponses aux questions du parcours
          (pouvant inclure des informations sensibles que vous choisissez de communiquer).
        </li>
        <li>
          <strong>Le voyage</strong> : vos réponses aux sessions, la phrase et le portrait
          rédigés à partir de ces réponses, la date de votre accord et votre attestation
          d&apos;avoir 15 ans ou plus.
        </li>
        <li>
          <strong>Notes du conseiller</strong> : les notes qu&apos;un conseiller prend sur votre
          analyse ou votre voyage pour préparer l&apos;entretien.
        </li>
        <li><strong>Paiement</strong> : traité par Stripe ; neoori ne voit jamais votre carte.</li>
      </ul>

      <h2>3. Finalités et bases légales</h2>
      <ul>
        <li>Génération du rapport d&apos;analyse — exécution du contrat.</li>
        <li>
          Le voyage : conservation de vos réponses, rédaction de la phrase et du portrait, prise
          en compte dans vos analyses — consentement, que vous retirez en supprimant votre voyage.
        </li>
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
      <p>
        Pour le voyage, le modèle reçoit vos réponses reformulées en mots simples — jamais de
        score chiffré — avec le prénom, la tranche d&apos;âge, la situation et le projet de votre
        profil, afin de rédiger la phrase et le portrait. Si vous avez fait le voyage, quelques
        lignes qui en résument les réponses accompagnent aussi vos analyses suivantes.
      </p>
      <p>
        Aucun terme médical, aucun diagnostic et aucune mention de votre statut administratif
        n&apos;est transmis au modèle. Lorsque vos conditions de travail sont renseignées,
        seules les conséquences sur le travail lui sont communiquées — jamais leur cause.
      </p>

      <h2>5. Destinataires et sous-traitants</h2>
      <ul>
        <li>Hostinger (hébergement de l&apos;application et de la base de données, Union européenne)</li>
        <li>Anthropic (génération IA, États-Unis — clauses contractuelles types)</li>
        <li>Stripe (paiement)</li>
      </ul>
      <p>
        Le lien de partage conseiller (« /c/… ») donne accès à une synthèse de votre analyse à
        toute personne disposant du lien : ne le transmettez qu&apos;à votre conseiller.
      </p>
      <p>
        Le lien conseiller du voyage (« /voyage/c/… ») ne s&apos;ouvre que pour un compte
        conseiller connecté. Il donne accès à la synthèse de vos réponses et à votre portrait,
        que le conseiller relit avec vous avant que vous le receviez.
      </p>

      <h2>6. Profil de base, voyage et conservation</h2>
      <p>
        Votre profil de base est conservé tant que votre compte est actif, afin que vous
        n&apos;ayez pas à le ressaisir et qu&apos;un conseiller qui vous accompagne puisse
        revenir sur votre dossier. Vous le supprimez à tout moment depuis votre espace ; la
        suppression est immédiate et définitive.
      </p>
      <p>
        <strong>Deux niveaux de stockage.</strong> Vos réponses ordinaires (identité, projet,
        contraintes pratiques) sont conservées telles quelles. Vos conditions de travail et,
        le cas échéant, votre statut de bénéficiaire de l&apos;obligation d&apos;emploi sont
        stockés séparément et chiffrés : ils n&apos;apparaissent ni dans les journaux
        techniques, ni dans les documents que vous téléchargez ou partagez, ni dans le rapport
        lui-même. Supprimer votre profil supprime les deux.
      </p>
      <p>
        Votre voyage est conservé tant que votre compte est actif ; vos réponses, votre phrase
        et votre portrait sont chiffrés et stockés séparément de votre profil. Vous le supprimez
        à tout moment depuis sa page : la suppression efface aussi les lignes du voyage
        recopiées dans vos analyses. Les rapports déjà rédigés ne sont pas modifiés.
      </p>
      <p>
        Vos analyses sont conservées tant que votre compte est actif. Vous pouvez supprimer
        chaque analyse individuellement depuis votre espace.
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
