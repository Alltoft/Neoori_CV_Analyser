# PM feedback — 2026-06-19 (form-only, no substance changes)

Source: PM WhatsApp voice note (2m49s, FR) + follow-up recap text. Praise overall
("très bon boulot"), synthèse is OK/coherent. All asks are **form**, not content.

## Confirmed decisions (do these)

### ✅ 0. Logo — DONE
Swapped to Mora's modified logo (little figure / "bonhomme" removed). Verify it's Mora's version.

### ✅ 1. Section 4 label — rename — DONE
Replaced **"Angles morts du CV (actuel)"** → **"Ce qui reste à renforcer"** in `page.tsx:20,88`.
Also reworded the 3 SEO meta strings (`layout.tsx:36,50,57`) "angles morts" → "points à renforcer".
Sites of truth:
- `frontend/src/app/page.tsx:20`  — `{ n: "4", title: "Angles morts du CV" }`
- `frontend/src/app/page.tsx:88`  — `{ n: "4", t: "Angles morts du CV actuel", free: true }`
- Consistency (SEO/meta + docs): `frontend/src/app/layout.tsx:36,50,57`, `CLAUDE.md:58`, `README.md:146`
  (these are descriptive prose "forces, angles morts et préconisations…" — reword sensibly,
  not necessarily verbatim "Ce qui reste à renforcer")

### ✅ 2. Hero title + accroche — replace — DONE
- Title `page.tsx:147–149` → **"Un CV,"** / gradient **"une cible."**
- Sous-titre `page.tsx:151–153` → **"Mesure l'adéquation en un clin d'œil."**
- CTA `page.tsx:428` → **"Prêt à mesurer l'adéquation d'un CV ?"** (my wording, drops orphaned
  "objectiver" — PM didn't give exact CTA text; confirm/adjust if she wants different).
- LEFT AS-IS: `AuthLayout.tsx:31` "…au regard de sa cible." — still consistent with "une cible"
  theme, not negative. Change only if PM wants.

> ⚠️ Not yet committed/pushed — copy changes are live on localhost:3001 only.

### 3. Title font → brand charte graphique
PM: current font reads like "Claude Code." No font name given — **infer the charter font.**
- Current display font = **Bricolage Grotesque** (`layout.tsx:2` import, `globals.css:10` `--font-display`).
- **Best inference:** the documented brand-redesign stack was **Plus Jakarta Sans** (display) + Inter (body)
  + JetBrains (mono); code later drifted to Bricolage. → revert display to **Plus Jakarta Sans**.
  Easy swap in `layout.tsx` next/font import + `--font-display` var. Validate visually; try 1–2 alts
  (Hanken Grotesk, Schibsted Grotesk) if Jakarta feels off.

### 4. Background — nuance off the "Claude" look
PM: warm-cream surfaces are recognizable as Claude's charte graphique. Pull surfaces toward
the **Neoori identity (navy #0f1e34 + orange #ff7a39)** — i.e. cooler/neutral, not terracotta-cream.
Tokens to retune in `frontend/src/app/globals.css`:
- `--paper #fdf7ec`  (warm cream — the main offender)
- `--accent / --peach-soft #fff0e3`
- `--secondary #f5f1ea`, `--muted #f3eee6`
Direction: replace warm-cream with a faint **cool / navy-tinted off-white** (e.g. try `--paper #f5f7fa`,
`--secondary #f1f3f7`, `--muted #eef1f6` — **proposals, tune live**). Keep orange as accent.
"Extract from Neoori identity" = sample the logo/brand assets; surfaces should sit in the navy family.

## Execution notes
- ⚠️ `frontend/AGENTS.md`: this Next.js is modified — read `node_modules/next/dist/docs/` before code.
  (These changes are copy/CSS/next-font — low risk, but heed it.)
- Use the `frontend-design` skill for #3/#4; run dev (`npm run dev` → port **3001**, set
  `BACKEND_URL=https://neoori-cv-analyser.onrender.com`) and screenshot to judge.
- Don't push until visually approved on localhost (per usual).

## Full transcript (verbatim, FR)
> Salam alaikum ! Je suis désolée de ne pas avoir été aussi présente, je suis très chargée
> professionnellement. J'ai quand même jeté un coup d'œil. [Imran], tu as fait du très très bon
> boulot — mais il y a toujours un petit "mais", rien d'important, du détail.
>
> Mora t'a envoyé le logo modifié ; celui que t'avais était un ancien. On voulait enlever le petit
> bonhomme qui était sur le côté.
>
> Toujours sur la forme : la synthèse est ok, cohérente. Par contre la petite synthèse en page de
> garde, section 4 : il y a marqué "Angle mort du CV". On avait modifié ça (c'est déjà modifié sur la
> synthèse). Reprends la modif — de mémoire on avait mis "amélioration" ou un truc comme ça — pour
> pas avoir de négativité dans la présentation.
>
> C'est fluide. Deux choses encore sur la forme : le fond — quand on connaît, on reconnaît le fond de
> Claude Code. Et la police de caractère. "Objectivée chaque CV au regard de sa cible" — peut-on
> utiliser une autre police pour correspondre à notre charte graphique ? Et "au regard de sa cible",
> j'ai un doute que ce soit parlant ; peut-être "au regard de son objectif". Genre "Optimiser chaque
> CV au regard de son objectif" — ça me paraît pas mal.

### Recap text (final, overrides audio where they differ)
> Pour récapituler : Le logo · Angles morts · police du titre + changer le titre et accroche par
> "Un CV, une cible" et sous-titre "Mesure l'adéquation en un clin d'œil". Pour le fond : nuancer un
> peu la couleur, car quand on connaît on reconnaît la charte graphique de Claude.
