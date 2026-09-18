# Open questions — profil dans le voyage

Raised while implementing `2026-09-18-profile-in-voyage.md` on 2026-09-18.
Nothing here blocked the build; each one names the assumption I shipped under, so
reversing it is a small change rather than a rewrite.

---

## 1. The three S4-derivable condition families — I did not derive them

**What I said earlier:** S4 already covers `rythme`, `environnement` and `relation`, so
the conditions step could ask only the five that are missing (`deplacements`,
`effort_physique`, `attention`, `consignes`, `organisation`).

**What I shipped:** all eight are asked, on one screen.

**Why I changed it:** deriving them means writing a mapping — does « open space vivant »
mean `environnement: me_convient`, or `possible_avec_adaptation`? That is a product
judgement about a field that feeds the OETH / aménagements layer, and inventing it
unsupervised is the wrong kind of initiative. Asking eight rows on one screen costs the
person one scroll; a wrong derivation costs them an inaccurate rights section.

**Decision needed:** should S4 pre-fill those three? If yes, the PM owns the mapping
table (S4 option → family → state), and `DIFFERENTIATING` should say whether a derived
value may ever count as a « point fort ». My instinct: a derived value should never be
a point fort — only a person saying so out loud.

---

## 2. `rayon` is retired, not deleted

Agreed in conversation: drop it, ville + bassin d'emploi replaces it.

**What I shipped:** the field is no longer asked anywhere, and `_profile_block` prints it
only for rows that already carry one. The column stays.

**Why:** dropping a populated column is irreversible and you were away. Say the word and
it is a three-line migration.

**Watch out:** nothing yet reads a bassin d'emploi. Until the BMO lookup exists, retiring
`rayon` means the prompt has *no* radius signal at all for new profiles — only a ville
string. That is a real (small) regression, accepted knowingly.

---

## 3. Which consent covers bloc 5?

**What I shipped:** a second consent — `consent_sensitive_at` / `consent_sensitive_version`
— required before non-empty conditions or a true OETH flag can be stored. The signup CGV
keeps covering the ordinary half.

**Why:** bloc 5 is health-adjacent and OETH is a disability status: GDPR Art. 9. A generic
CGV tick at signup, before the person has seen what the product does, is not specific and
informed consent for that.

**Decision needed:** the exact French wording of the second consent, and whether
`CONSENT_SENSITIVE_VERSION` should track the CGV version or move independently. I used
`v1` and a plain sentence; it wants a legal read before it ships to prescribers.

---

## 4. The PM's two PDFs still do not ask for four things

Unchanged since the review, and out of scope of this plan because they are not mine to
invent:

| Missing | Consequence |
|---|---|
| `projet` / cible visée | Analyses still collect it on their own form, so nothing breaks — but the profile no longer pre-fills it |
| Module Pont placement | It runs post-portrait and optional, so it feeds no analysis. Bloc 4 stays thin |
| The CV | Never mentioned in either PDF |
| A bassin-d'emploi lookup | `demande_locale` has no data source in this codebase yet |

---

## 5. Age brackets — done, but the routing comment is still fiction

Option A shipped: `14_17 · 18_21 · 22_24 · 25_34 · 35_44 · 45_54 · 55_plus`, with
`moins_25` accepted and never offered.

`backend/app/models/profile.py` still claims brackets « route the Académie des Ori variant
and gate the youth schemes in parcours 3 ». Grep finds no such branch. It is a plan, not a
behaviour — and whoever writes it now writes it against seven values plus a legacy one.

---

## 6. Is `situation` really staying?

I kept it (entry step, one question) because nothing else tells the model « en poste
wanting to move » from « première insertion », and grep confirms it costs one prompt line.
But the PM's PDFs never ask it, and his audience — a 16-year-old choosing a school — has
no meaningful answer to it. If the youth parcours is the only one that uses the voyage,
`situation` could move to the analysis form instead and leave the voyage alone.

---

# Handoff — what shipped, and what you need to know

Branch `feat/profile-in-voyage`, 7 commits off `initial`. Nothing pushed.

**Verification at handoff:** `893 passed` (backend, was 859 at branch point) ·
`npx tsc --noEmit` clean · `npx next build` succeeds, `/voyage/etape/[bloc]`
listed · `npx eslint src/` shows 5 errors, all in files this branch did not
create (`react-hooks/set-state-in-effect` in `lib/auth.tsx`,
`admin/analyses`, `admin/prompts`, `espace`, and `react-hooks/purity` in
`analyse/en-cours/[id]`) — same five as before the branch.

## 7 · Read this first: my commits contain some of your uncommitted work

Your tree had 45 uncommitted files when I started (the voyage neutral / ranked
choices / no-billet work, plus the two PDFs and migration `b4c5d6e7f8a9` as
untracked files). I branched rather than committing on `initial`, but several
files I had to edit were already modified — `models/voyage.py`,
`types/voyage.ts`, `voyage-labels.ts`, `voyage/page.tsx`,
`voyage/session/[n]/page.tsx`, `test_voyage_routes.py`,
`test_voyage_parity.py`, `test_voyage_prompt_context.py` — and staging them
swept your changes in alongside mine.

**Nothing is lost**, and 34 files are still uncommitted on the branch. But my
commits are not purely mine, and the diffs will read larger than the work.
If you want them separated, `git reset --soft initial` and re-stage by hand —
you lose the commit messages, which is the only real cost.

I did **not** touch `TEST-PLAN.md` for exactly this reason, so several of its
rows are now stale:

| Row | Now wrong because |
|---|---|
| 3.1.1 | `/profil` has seven cards — « Votre parcours » is inserted as *2 bis* |
| 3.1.2 | Rayon is read-only and only shown to rows that have one; brackets are seven, not five |
| 3.2.x | Bloc 5 is not saved until the new bloc-6 consent is ticked |
| 12 preamble | S1 wants prénom + tranche d'âge (now from signup); S2–S5 also want the parcours block, S5 the conditions step |

## What is built

- 7 age brackets meeting at 25, `moins_25` accepted and never offered
- 4 parcours columns + 2 sensitive-consent columns, two idempotent migrations
  (`c5d6e7f8a9b0`, `d6e7f8a9b0c1`) and a test that the revision graph has one head
- `session_lock` gates S2–S5 on the parcours block and S5 on the conditions step
- Signup seeds prénom + tranche d'âge; the entry block sits on the hub's gate;
  `/voyage/etape/<bloc>` serves parcours and conditions
- `_profile_block` carries the parcours lines; `rayon` prints only for rows
  that still hold one

## What is not built

1. **Module Pont (FP-1…FP-14).** Post-portrait, optional, feeds no analysis.
2. **The bassin d'emploi lookup.** `ville` is collected and reaches the prompt,
   but nothing reads BMO, so « demande locale » has no source. Retiring `rayon`
   means new profiles now carry no radius signal at all until this exists.
3. **The counselor sheet does not show the parcours block.** `/voyage/c/<token>`
   still shows prénom, tranche d'âge, situation. Adding diplôme and appétence
   there is a few lines and probably wanted — I left it because the counselor
   view was not in the scope we discussed.
4. **No browser pass.** Everything is verified by tests, types and a
   production build; I did not run the app and click through the new steps.

## Two judgement calls I made alone

- **All eight condition families are asked**, not the five I said. Deriving the
  other three from S4 means inventing a mapping that feeds the rights section.
  See §1 above.
- **`rayon` is retired, not dropped**, and the column stays. See §2 above.
