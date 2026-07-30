# Manual test plan — CDC v1.2 / Parcours build

Test environment: https://frontend-seven-fawn-59.vercel.app

Work through in order. Each row is: what to do → what should happen. Anything
that doesn't match, note the URL and what you saw.

---

## Read this before you start

**Two things will fail until the PM acts, and that's expected — not a bug:**

| What | Why | Symptom |
|---|---|---|
| Parcours 2 and 3 generation | No prompt exists for them yet | Analysis goes to `erreur` with "Aucun prompt actif pour le chemin 2" (or 3) |
| Free-tier "verdict" quality | The current P1 prompt predates the verdict section | The section will exist and be filled, but the wording may be off — the schema forces the key, the prompt never described what belongs in it |

The **forms** for parcours 2 and 3 are fully testable (validation, upload,
navigation) — only the generation step is blocked.

Everything else below should work end to end.

---

## 1 · Entry and navigation

| # | Do | Expect |
|---|---|---|
| 1.1 | Open the landing page | Colours have changed: orange is deeper (`#EA5624`, was a brighter coral), navy is lighter/bluer (`#1C3561`), backgrounds have a faint green tint instead of blue |
| 1.2 | Click any "Lancer mon analyse" / "Démarrer" CTA | Lands on **`/analyse`** — a 3-card chooser, *not* the form directly. This is new; there were 12 CTAs that all went straight to the parcours-1 form |
| 1.3 | Check the landing report preview | Shows §1, §2, §3 only. The locked strip below now starts at **§4** |
| 1.4 | Landing FAQ + pricing card | Say "sections 1 à 3 et le verdict de diagnostic", not "1 à 4" |
| 1.5 | Read the CGV (`/cgv`) | Section 2 says free = sections 1 à 3 + verdict, and lists "les points à renforcer" in the paid offer |
| 1.6 | Try `/analyse/orientation` directly | 404 — the old b1/b2/b3 form is deleted |

---

## 2 · The chooser

| # | Do | Expect |
|---|---|---|
| 2.1 | Open `/analyse` | Three cards: "J'ai une cible", "Je cherche ma direction", "Je pars de zéro" |
| 2.2 | Read the badges | Cards 1 and 2 say "CV requis", card 3 says "Aucun CV nécessaire" |
| 2.3 | Click each card | → `/analyse/nouveau`, `/analyse/direction`, `/analyse/depart` |
| 2.4 | Check the footer link | "Compléter mon profil" → `/profil` |

---

## 3 · Profil de base — `/profil`

**You need to be logged in.** Create an account first if needed.

| # | Do | Expect |
|---|---|---|
| 3.0 | Log out, then open `/profil` directly | Bounced straight to `/connexion?redirect=/profil` — you should never see the form. After logging in you land back on the profile |

### 3.1 Structure

| # | Do | Expect |
|---|---|---|
| 3.1.1 | Open `/profil` | Six numbered blocks: Vous · Votre situation · Votre projet · Contraintes pratiques · Conditions de travail · Droits et accord |
| 3.1.2 | Bloc 1 | Prénom, Nom, **Ville**, **Rayon de recherche** (4 options), **Tranche d'âge** (5 brackets). Radius and age bracket are both new |
| 3.1.3 | Type a lowercase name | Forces itself to UPPERCASE as you type |
| 3.1.4 | Bloc 2 | Five situations. **There is no separate "type de mobilité" field any more** — the PM merged it in here |
| 3.1.5 | Bloc 2 → pick "En reconversion" | A sub-question appears: rester dans mon domaine / changer de métier / changer de secteur |
| 3.1.6 | Switch away from "En reconversion" | The sub-question disappears and the answer is cleared |
| 3.1.7 | Bloc 3 | Free-text projet **plus** an optional PDF drop zone for a job ad / fiche de poste |
| 3.1.8 | Bloc 4 | Amber warning box: "N'indiquez aucune information de santé, aucun diagnostic, aucun traitement…" |

### 3.2 Bloc 5 — the conditions matrix (this is the biggest new piece)

| # | Do | Expect |
|---|---|---|
| 3.2.1 | Look at bloc 5 | Eight families (Rythme, Environnement, Déplacements, Effort physique, Attention, Relation, Consignes, Organisation), each with 3 radio states + a separate "point fort" checkbox |
| 3.2.2 | Each family row | Shows examples underneath ("horaires réguliers, variables, tôt le matin…") |
| 3.2.3 | Resize to mobile width | Rows stack; state labels become visible text instead of icon-only columns |
| 3.2.4 | Tick "Me convient" on **Environnement** | Live synthesis panel shows it under **"Ce qui vous convient"** |
| 3.2.5 | Now also tick "point fort" on Environnement | It **also** appears under "Vos points forts", and a note appears explaining a point fort is an exigence few people tolerate |
| 3.2.6 | Tick "point fort" on **Consignes** instead | It does **NOT** appear under "Vos points forts" — this is deliberate. Only demanding requirements (rythme, environnement, déplacements, effort physique) count as differentiators |
| 3.2.7 | Set something to "À éviter" | Appears under "À éviter" in the synthesis, live, with no page reload |

> 3.2.6 is the rule the PM cares about: *« me convient » n'est pas un point fort.*
> If it appears there, that's a bug.

### 3.3 Bloc 6 and the consent gate

| # | Do | Expect |
|---|---|---|
| 3.3.1 | Scroll to bloc 6 | OETH checkbox with an explainer, then a separate RGPD consent checkbox |
| 3.3.2 | Leave consent unticked | The "Enregistrer et continuer" button is **greyed out and unclickable** |
| 3.3.3 | Tick consent | Button becomes active |
| 3.3.4 | **Tick the OETH box** | **Nothing else on the page changes.** No new field, no re-layout, no extra loading. This is the spec rule — if anything reacts, the person learns they just flagged themselves |
| 3.3.5 | Save, then reload `/profil` | Everything comes back, **including** the OETH checkbox state and all bloc 5 answers |

### 3.4 Erasure

| # | Do | Expect |
|---|---|---|
| 3.4.1 | Read `/confidentialite` § 6 | Now describes the persistent profile, the two storage levels, and that conditions + OETH are encrypted and excluded from logs, downloads and the report |

---

## 4 · Parcours 1 — `/analyse/nouveau`

| # | Do | Expect |
|---|---|---|
| 4.1 | Fill and submit a real CV + target | Analysis runs, lands on the report |
| 4.2 | Count the sections on a **free** report | **§1, §2, §3 + a "Verdict" section.** §4 is no longer free |
| 4.3 | Check section §3 | Renders as a tag cloud, not paragraphs |
| 4.4 | Check the CTA banner | "Débloquez les **6** sections restantes" (was 5) |

---

## 5 · Parcours 2 — `/analyse/direction`

Generation is blocked (no prompt). Test the form itself.

| # | Do | Expect |
|---|---|---|
| 5.1 | Open the page | CV drop zone + paste area, then **three** questions: satisfaction / ce que vous ne voulez plus / raison du changement |
| 5.2 | Submit with everything empty | Four inline errors in French |
| 5.3 | Type 5 characters in a question | Still errors — 20-character minimum |
| 5.4 | Upload a PDF CV | Filename shows, drop zone turns green |
| 5.5 | Fill everything and submit | Reaches the generation screen, then fails with "Aucun prompt actif pour le chemin 2" — **expected until the prompt exists** |

---

## 6 · Parcours 3 — `/analyse/depart`

| # | Do | Expect |
|---|---|---|
| 6.1 | Open the page | **Five** questions, **no CV upload anywhere** |
| 6.2 | Read question 1 | Mentions jobs, petits boulots, bénévolat, sport, garde d'un proche — "Rien n'est trop petit" |
| 6.3 | Type 12 characters in each | **Accepted.** Deliberately lower than parcours 2 — this parcours exists for people without a CV |
| 6.4 | Submit | Same expected prompt error as 5.5 |

---

## 7 · The report and the paywall

| # | Do | Expect |
|---|---|---|
| 7.1 | Open a free report | Below the unlock CTA: **"Ce diagnostic vous a-t-il été utile ? Selon vous, il vaudrait :"** with 5 buttons (moins de 5 € → je ne paierais pas) |
| 7.2 | Click one | Replaced by "Merci — ça nous aide à ajuster." |
| 7.3 | Reload and check | The probe stays answered (one answer per analysis) |
| 7.4 | Go to `/analyse/<id>/debloquer` | Free card lists §1–§3, struck-through §4–§9. Paid card 9 €. **New: a third "Premium" card below** |
| 7.5 | Read the Premium card | 24 € (default — the PM sets the real price), listing §10 préparation à l'entretien and §11 questions difficiles |
| 7.6 | Try clicking Premium without the waiver checkbox | Disabled, says "Cochez la renonciation ci-dessus pour continuer" |

> Stripe is in test mode / may be disabled. If so both buttons say
> "Paiement bientôt disponible" — that's the config, not a bug.

---

## 8 · Counselor view

| # | Do | Expect |
|---|---|---|
| 8.1 | On a report, click "Partager au conseiller", open the copied link | Opens `/c/<token>` with a VERSION CONSEILLER badge |
| 8.2 | Check the sections | Shows the counselor set only, **and every section has content** — previously a Chemin B share link rendered three empty grey skeletons |
| 8.3 | Switch to "Vue conseiller" on the report page itself | Same section set |

---

## 9 · Admin — `/admin`

| # | Do | Expect |
|---|---|---|
| 9.1 | `/admin/prompts` | The selector now shows **three** parcours: P1 · J'ai une cible / P2 · Je cherche ma direction / P3 · Je pars de zéro (was "Chemin A / Chemin B") |
| 9.2 | Switch between them | Each has its own version history. P2 and P3 say "Aucune version pour le parcours…" |
| 9.3 | **Paste and publish the P1 prompt** | New version appears, labelled with a `-P1` suffix |
| 9.4 | `/admin/couts` | **Three** token columns (Gratuit / Payant / Premium) instead of two, and each shows the model name it bills |
| 9.5 | Check the model names | `claude-haiku-4-5`, `claude-sonnet-5`, `claude-opus-5` |
| 9.6 | `/admin` overview | The "prompt actif" tile no longer shows a random parcours' version |

---

## 10 · Print / PDF

| # | Do | Expect |
|---|---|---|
| 10.1 | Open a report, click "PDF" | Print preview opens |
| 10.2 | Check the page shape | Content fills an A4 page properly. The on-screen card is now A4-proportioned (was 2:3, so what you saw didn't match what printed) |
| 10.3 | Check a long report | Content flows onto page 2 instead of being cut off |
| 10.4 | Check the printed output | No nav bar, no tabs, no unlock CTA, no price probe |

---

## 11 · Security spot-check (optional but worth one minute)

| # | Do | Expect |
|---|---|---|
| 11.1 | Log in as user A, create an analysis, copy its URL | — |
| 11.2 | Log out, log in as user B, open that URL | **"Accès non autorisé"** — previously this returned the full analysis including the CV text |

---

## What to report back

For each failure: the step number, the URL, and what you saw instead.

Worth flagging to the PM specifically, whatever the outcome:

1. **The free tier narrowed** — §4 "Ce qui reste à renforcer" moved to paid, per CDC §4. The CGV now says so. That's a contract change and needs their sign-off.
2. **A profile now requires an account.** Neither document says this explicitly; it follows from the persistent-profile decision.
3. **Premium is priced at 24 € by default** — the middle of their "2–3× the paid tier". They should confirm or change it.
4. **The verdict section needs prompt text.** The free tier now asks for it and the schema guarantees the key exists, but no prompt describes what belongs in it yet.
