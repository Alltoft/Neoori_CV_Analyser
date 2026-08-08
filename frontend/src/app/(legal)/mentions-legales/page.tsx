export const metadata = { title: "neoori — Mentions légales" }

// Required by LCEN (loi n° 2004-575). [À COMPLÉTER] fields must be filled
// before live payments are enabled.
export default function MentionsLegalesPage() {
  return (
    <article>
      <h1>Mentions légales</h1>

      <h2>Éditeur du site</h2>
      <p>
        <strong>[À COMPLÉTER : dénomination sociale / nom du micro-entrepreneur]</strong><br />
        Forme juridique : [À COMPLÉTER : micro-entreprise, SASU, …]<br />
        SIREN / SIRET : [À COMPLÉTER]<br />
        Siège social : [À COMPLÉTER : adresse complète]<br />
        Contact : [À COMPLÉTER : email] · [À COMPLÉTER : téléphone — facultatif]
      </p>
      <p>Directeur·rice de la publication : [À COMPLÉTER : nom du responsable légal]</p>

      <h2>Hébergement</h2>
      <p>
        Application et base de données : Hostinger International Ltd., 61 Lordou Vironos Street,
        6023 Larnaca, Chypre — hostinger.fr<br />
        Serveur privé virtuel situé dans l&apos;Union européenne — data center de
        Francfort-sur-le-Main, Allemagne
      </p>

      <h2>Propriété intellectuelle</h2>
      <p>
        L&apos;ensemble du site neoori (textes, interface, marque) est protégé par le droit de la
        propriété intellectuelle. Toute reproduction sans autorisation est interdite. Les rapports
        d&apos;analyse générés appartiennent à l&apos;utilisateur qui les a commandés.
      </p>

      <h2>Médiation de la consommation</h2>
      <p>
        Conformément à l&apos;article L612-1 du Code de la consommation, le consommateur peut recourir
        gratuitement à un médiateur de la consommation : [À COMPLÉTER : nom et coordonnées du
        médiateur choisi — obligatoire dès les premières ventes].
      </p>
    </article>
  )
}
