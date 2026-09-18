# PM site audit — 2026-09-18 — DEFERRED, do not build now

Source: PM walkthrough of the live site (https://neoori.tech), 18 steps, full landing page.
Overall verdict: **7/10** — "bien conçu, design professionnel, discours clair, positionnement
différenciant (secteur public de l'emploi). Les fondamentaux sont là."

**Status: parked on purpose.** Decision 2026-09-18: ship and use the app as-is. This list is
conversion polish, not blockers. Revisit **when we have real clients** (first paying users or
first named partner structure) — several items (social proof, usage figures, partner logos)
literally cannot be done before then.

---

## Verified before parking

Two claims were checked against the source the same day:

| Claim | Verdict |
|---|---|
| "Typo d'email — `nneoori@proton.me` (deux n)" | **FALSE.** That is the real mailbox, spelled correctly. `frontend/src/app/page.tsx:166` and `:598`. Do not "fix" it. The *branded-address* point (below) still stands. |
| "Pas de canonical / JSON-LD / hreflang" | **TRUE.** No `canonical`, no `application/ld+json`, no `hreflang` anywhere in `frontend/src`. |

---

## What the PM praised (don't regress these)

- **Hero** — two-column layout, Plus Jakarta Sans + Inter, terracotta accent, floating report
  preview. Called "la meilleure décision de la page : on comprend l'output en 3 secondes."
- **Palette** — navy + terracotta + off-white, single accent colour, discipline held.
- **« Le Voyage » navy section** — works as emotional punctuation.
- **Three parcours cards** — distinct colour codes; "un excellent cadrage métier qui montre une
  vraie compréhension du terrain."
- **Report mockup** — locked (padlock) vs unlocked (green check) sections communicates freemium
  instantly.
- **Tone** — « Votre CV a des choses à dire. Aidez-le à les dire. » = "chaleureux sans être niais."
- **Pricing grid** — gratuit → 9 € → code conseiller, "limpide"; « Le plus choisi » badge well placed.
- **RGPD / EU hosting / no AI training section** — essential for France Travail, Mission Locale,
  Cap Emploi.
- **All images have `alt`.** Accessibility + SEO.
- **Perf** — DOMContentLoaded 630 ms, load 950 ms. Mobile responsive OK, no overflow.

---

## Deferred backlog

Ordered by the PM's own priority reading, with our sizing.

### P1 — cheap, do first when we reopen this

1. **Branded email address.** Proton address on a non-owned domain weakens credibility with public
   organisations. Fix = MX record to Proton, or a forward: `contact@neoori.tech` →
   `nneoori@proton.me`. Touches `page.tsx:166` and `:598`. DNS work, not code work.
2. **Cookie consent banner.** PM's sharpest point: we *sell* RGPD compliance, so shipping analytics
   without a consent banner is an inconsistency "rapidement repérée par un acheteur public."
   → First confirm whether any analytics script actually ships. No script = no banner needed, and
   that is worth saying out loud in the FAQ instead.
3. **SEO completion.** Add `canonical`, a `SoftwareApplication`/`Service` JSON-LD block (with price),
   and `hreflang="fr"`. Meta description is 158 chars — acceptable, at the limit.

### P2 — needs real clients first (that's the point of parking)

4. **Social proof — the biggest conversion gap.** Page has zero testimonials, zero usage figures,
   zero named partner. "Camille D." in the mockup is illustrative, not credible as proof. Wanted:
   - 2–3 short quotes from counselors or candidates (first name, role, structure if allowed)
   - 2–3 partner logos, even just an « ils nous font confiance » strip
   - one key figure (« X analyses réalisées » / « X candidats accompagnés »)
5. **Real example report.** « Voir un exemple de rapport » currently scrolls to `#rapport`, a static
   mockup. For a product whose whole value *is* the report, an anonymised downloadable PDF — or an
   interactive sample — is called "un levier de conversion majeur". Today we ask 9 € on trust alone.
6. **Reframe the BÊTA badge.** Generic "Bêta" can spook public buyers who need RGPD and hosting
   commitments. If it really is a pilot, say so: « en pilote avec X structures » — which again needs
   at least one named structure.

### P3 — nice to have

7. **FAQ depth.** Six questions is thin for freemium + B2B. Missing, per PM:
   - « Que se passe-t-il avec mes données après l'analyse ? » (beyond the generic RGPD line)
   - « L'IA peut-elle se tromper dans son analyse ? »
   - « Puis-je utiliser neoori sans conseiller ? »
   - « Le CV retravaillé est-il garanti de passer les ATS ? »
   (Accordion itself works fine.)
8. **JS payload.** 74 resources, 21 JS files, 778 KB for a largely static landing page. "C'est le
   coût de Next.js mais c'est excessif." Worth a look, not a rewrite.
9. **Font loading.** Plus Jakarta Sans 200, Inter 100–400, JetBrains Mono 100–400 reported as
   *unloaded* → FOUT risk on some configs. Trim the weights we don't use.
10. **Hero image resolution.** Served at `w=640&q=75`; may look soft on Retina. Bump the width.
11. **Scrollspy.** Nav doesn't highlight the active section.
12. **Mobile hamburger menu untested** by the PM — verify it at some point.
13. **No blog / resources section.** Missed SEO and authority play in a very competitive space
    (emploi, CV, orientation). Big effort, long payoff — genuinely later.

---

## Full PM verdict, verbatim

> neoori.tech est un site bien conçu, avec un design professionnel, un discours clair et un
> positionnement différenciant (secteur public de l'emploi). Les fondamentaux sont là. Mais pour un
> produit qui demande 9 € par analyse et qui cible des organisations publiques, plusieurs éléments
> freinent la conversion : pas de preuve sociale, un exemple de rapport non cliquable, une typo
> d'email, et l'absence de bannière cookies qui contredit le discours RGPD. Ce sont des corrections
> rapides qui élèveraient le site de « bon » à « convaincant ».
