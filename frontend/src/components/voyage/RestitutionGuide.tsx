"use client"

/**
 * The counselor manual's page-23 guide, reproduced verbatim: five phases, the
 * page-2 wording rules and the « Phrases utiles en restitution » list.
 *
 * Static content — no props and no data. Every string sits in a TS constant
 * rather than in JSX text, so the manual's straight apostrophes survive
 * untouched (a bare « ' » in JSX trips react/no-unescaped-entities).
 *
 * Reproduced as written, including PHASE 05's « Simulateur d'aménagement »: the
 * simulator is out of v1 (spec § Out of scope), but this page is a paper
 * protocol the counselor runs in the room, not a feature index.
 *
 * COUNSELOR SURFACE ONLY — the guide names the frameworks out loud.
 */

const GUIDE_TITLE = "Guide de conduite de l'entretien"
const GUIDE_SUBTITLE = "Durée totale recommandée : 40 min · 5 phases"
const WORDING_TITLE = "Rappel — Principes du wording de restitution"
const PHRASES_TITLE = "Phrases utiles en restitution"

const PHASES: { n: string; title: string; duration: string; rows: [string, string][] }[] = [
  {
    n: "01",
    title: "Accueil & posture",
    duration: "5 min",
    rows: [
      [
        "Rappel du cadre",
        "Confidentialité · Pas de bonne réponse · Le portrait dit « ce que tu m'as dit de toi »",
      ],
      [
        "Posture du conseiller",
        "Ami intelligent, pas expert RH. Curiosité, pas jugement. Laisser des silences.",
      ],
      [
        "Ouverture",
        "Demander au jeune : « Qu'est-ce qui t'a surpris dans les questions ? » avant de lire le portrait.",
      ],
    ],
  },
  {
    n: "02",
    title: "Lecture du portrait",
    duration: "10 min",
    rows: [
      [
        "Lire à voix haute",
        "La phrase d'accroche en premier. Pause. Observer la réaction.",
      ],
      [
        "Vérifier la résonance",
        "« Est-ce que tu te reconnais là-dedans ? » — Ne pas argumenter si le jeune dit non.",
      ],
      [
        "Ajuster si besoin",
        "Si un élément ne correspond pas, c'est une donnée. Creuser : « Qu'est-ce qui ne colle pas ? »",
      ],
      [
        "Section 5 (chemins)",
        "Ne pas nommer de métier. Laisser le jeune faire le lien lui-même.",
      ],
    ],
  },
  {
    n: "03",
    title: "Exploration des tensions",
    duration: "10 min",
    rows: [
      [
        "Nommer les tensions S0",
        "« J'ai noté une ambivalence sur [axe]. Tu as autant coché des deux côtés. Qu'est-ce que ça t'évoque ? »",
      ],
      [
        "Questions ouvertes",
        "« À quel moment tu te sens le plus toi-même ? » · « Qu'est-ce qui te manquerait si... ? »",
      ],
      [
        "Valeur centrale (S5-4)",
        "« Ce qui te met en colère, c'est [valeur bafouée]. Comment tu vois ça dans ce qui t'attire professionnellement ? »",
      ],
    ],
  },
  {
    n: "04",
    title: "Les chemins possibles",
    duration: "10 min",
    rows: [
      [
        "Repartir du RIASEC",
        "Nommer les 3 univers RIASEC (ex : « Réaliste, Entreprenant, Investigateur ») et leur traduction concrète.",
      ],
      [
        "Environnement avant métier",
        "Demander : « Dans quel type de lieu tu t'imagines travailler ? » — Taille structure, terrain/bureau, rythme.",
      ],
      [
        "Associations",
        "« Si tu penses à des adultes autour de toi qui semblent épanouis dans leur travail — qu'est-ce qu'ils ont en commun ? »",
      ],
      [
        "3 pistes concrètes",
        "Proposer 3 univers professionnels (pas des métiers) en lien avec le profil. Inviter le jeune à en explorer 1.",
      ],
    ],
  },
  {
    n: "05",
    title: "Clôture & suite",
    duration: "5 min",
    rows: [
      [
        "Résumé en 3 mots",
        "Demander au jeune : « Si tu devais résumer ce que tu retiens en 3 mots, ce serait quoi ? »",
      ],
      [
        "Simulateur d'aménagement",
        "Proposer si pertinent. Expliquer : « Ça va plus loin — ça aide à formuler ce dont tu as besoin pour bien travailler. »",
      ],
      [
        "Action concrète",
        "1 action entre maintenant et la prochaine séance : une recherche, une rencontre, une visite.",
      ],
      [
        "Mot final",
        "Terminer par : « Ce portrait n'est pas ce que tu dois devenir. C'est ce que tu es déjà. »",
      ],
    ],
  },
]

/** Page 2 — what never to say, and what to say instead. */
const WORDING: [string, string][] = [
  ["« Tu es... »", "« Tu as tendance à... » / « Tu sembles plus à l'aise quand... »"],
  [
    "« Tu es créatif. »",
    "« Tu es créatif lorsque tu as une marge de liberté. » — Trait + Condition.",
  ],
  [
    "« manque », « faible », « limite »",
    "« moins stimulant pour toi » / « peut te demander plus d'énergie »",
  ],
  ["« handicap », « difficulté »", "« besoin spécifique », « préférence cognitive »"],
  [
    "« résultats », « score »",
    "« ce que tu m'as dit de toi » / « ce que je lis dans tes choix »",
  ],
]

const PHRASES: string[] = [
  "« Ce n'est pas moi qui te dis qui tu es. C'est toi qui me l'as dit, à travers tes choix. »",
  "« Il n'y a pas de profil idéal. Il y a un profil qui correspond à des environnements. »",
  "« Ce dont tu as besoin n'est pas un problème à résoudre. C'est une information à utiliser. »",
  "« On cherche pas le métier. On cherche d'abord le cadre dans lequel tu te révèles. »",
  "« Ce portrait n'est pas ce que tu dois devenir. C'est ce que tu es déjà. »",
]

/** The manual's « Mes notes de restitution » prompts. The page shows them above
 *  the private note field, which is where the counselor answers them. */
export const NOTE_PROMPTS: string[] = [
  "Réaction du jeune à la phrase d'accroche :",
  "Ce qui l'a le plus surpris / touché :",
  "Ce qu'il/elle a nuancé ou contesté :",
  "Action retenue pour la prochaine séance :",
]

function TwoColumnTable({
  head,
  rows,
}: {
  head: [string, string]
  rows: [string, string][]
}) {
  return (
    <table className="w-full text-left text-xs">
      <thead>
        <tr className="border-b border-border">
          <th className="eyebrow w-1/3 py-1 pr-3 text-muted-foreground">{head[0]}</th>
          <th className="eyebrow py-1 text-muted-foreground">{head[1]}</th>
        </tr>
      </thead>
      <tbody>
        {rows.map(([left, right]) => (
          <tr key={left} className="border-b border-border/60 align-top">
            <td className="py-1.5 pr-3 font-medium text-navy">{left}</td>
            <td className="py-1.5 leading-relaxed text-muted-foreground">{right}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

export function RestitutionGuide() {
  return (
    <div className="mt-8">
      <h2 className="eyebrow text-orange-dark">Restitution</h2>
      <h3 className="mt-1 font-display text-lg font-bold text-navy">{GUIDE_TITLE}</h3>
      <p className="mt-0.5 text-xs text-muted-foreground">{GUIDE_SUBTITLE}</p>

      <section className="print-break mt-4 rounded-lg border border-border p-4">
        <h4 className="font-display text-sm font-semibold text-navy">{WORDING_TITLE}</h4>
        <div className="mt-3">
          <TwoColumnTable head={["À ne jamais dire", "À utiliser à la place"]} rows={WORDING} />
        </div>
      </section>

      {PHASES.map((phase) => (
        <section key={phase.n} className="print-break mt-4 rounded-lg border border-border p-4">
          <div className="flex items-baseline justify-between gap-3">
            <h4 className="font-display text-sm font-semibold text-navy">
              {`PHASE ${phase.n} — ${phase.title}`}
            </h4>
            <span className="shrink-0 font-mono text-[11px] text-muted-foreground">
              {phase.duration}
            </span>
          </div>
          <div className="mt-3">
            <TwoColumnTable head={["Point clé", "Comment faire"]} rows={phase.rows} />
          </div>
        </section>
      ))}

      <section className="print-break mt-4 rounded-lg bg-peach-soft p-4">
        <h4 className="font-display text-sm font-semibold text-navy">{PHRASES_TITLE}</h4>
        <ul className="mt-2 space-y-1.5">
          {PHRASES.map((phrase) => (
            <li key={phrase} className="text-xs leading-relaxed text-navy">
              {phrase}
            </li>
          ))}
        </ul>
      </section>
    </div>
  )
}
