# Manual test plan — CDC v1.2 / Parcours build

Test environment: http://localhost:8080 (docker dev) — VPS domain after cutover (see DOCKER.md)

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

**Every analysis currently runs the PAID tier.** While the PM judges report
*content*, the free tier's three sections aren't what needs reviewing, so the
tier selection is overridden. Practical effects:

- Every new report comes back with all 9 sections, no lock icons.
- The free-tier **verdict** section and the **willingness-to-pay probe** won't
  appear — they're free-tier only. Skip **§ 7.1–7.3** and the free-tier half of
  **§ 4.2** for now.
- `/debloquer` will say "Cette analyse est déjà complète" for new analyses,
  because they are. To see the paywall and the Premium card (**§ 7.4–7.6**),
  open an analysis created *before* today.

Reverting is one env var: `FORCE_ANALYSIS_TIER=""` on Render.

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
| 9.1 | `/admin/prompts` | The selector shows **five** prompts, in this order: Parcours 1 · J'ai une cible / Parcours 2 · Je cherche ma direction / Parcours 3 · Je pars de zéro / Voyage · phrase (S0) / Voyage · portrait (was three parcours, and before that "Chemin A / Chemin B") |
| 9.2 | Switch between them | Each has its own version history. A prompt with no version yet says « Aucune version pour … » followed by that prompt's name |
| 9.3 | **Paste and publish the P1 prompt** | New version appears, labelled with a `-P1` suffix |
| 9.4 | `/admin/couts` | **Three** token columns (Gratuit / Payant / Premium) instead of two, and each shows the model name it bills |
| 9.5 | Check the model names | `claude-haiku-4-5`, `claude-sonnet-5`, `claude-opus-5` |
| 9.6 | `/admin` overview | The "prompt actif" tile no longer shows a random parcours' version |
| 9.7 | Read the help line under the chips | It names the selected prompt and says what that prompt produces — the report sections for a parcours, the phrase or the six portrait sections for the voyage. The word « parcours » never appears for the two Voyage entries |
| 9.8 | Click « Voyage · phrase (S0) » | The editor loads the seeded text, the badge reads `v1.0-VM · actif`, and the help line describes the phrase written just after la session 0 |
| 9.9 | Click « Voyage · portrait » | The editor loads the seeded text, the badge reads `v1.0-VP · actif`, and the help line lists the six sections |
| 9.10 | Change one word in the portrait prompt, click « Publier la nouvelle version » | A new version appears at the top of the history, labelled with a `-VP` suffix and marked `actif`; the previous one now offers « Rollback » |
| 9.11 | Switch back to « Parcours 1 · J'ai une cible » | Its history is unchanged — no `-VM` or `-VP` version appears in it, and the editor still shows the parcours 1 prompt |
| 9.12 | Click « Rollback » on the previous `-VP` version, confirm | It becomes `actif` again and the editor reloads its text |

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

## 12 · Le voyage

**You need to be logged in.** Sessions 1 to 5 additionally need a counselor code
and a Profil de base with at least a prénom and a tranche d'âge — that is the
gate, not a bug.

Text that comes from the paper cahier — session titles, scenes, the portrait —
says *tu* wherever it appears. Everything the app adds — buttons, cards,
banners, error messages — says *vous*. If you find a *tu* on a button or a
*vous* inside a session, that is a bug.

### 12.1 Entry points

| # | Do | Expect |
|---|---|---|
| 12.1.1 | Open the landing page and scroll past the hero | A navy band, eyebrow "Le voyage", heading « Avant de parler de poste, parlons de vous. », **above** the three scenario cards |
| 12.1.2 | Click « Commencer le voyage » while logged out | `/connexion?redirect=/voyage`, and after logging in you land on `/voyage` |
| 12.1.3 | Open `/analyse` | A full-width navy card, "Le voyage" / « Mon cahier d'exploration », **above** the three parcours cards. The three cards themselves are unchanged |
| 12.1.4 | Open `/espace` with no voyage started | A navy strip at the very top offering to start, reading "Six sessions pour poser ce que vous savez déjà de vous." It never blocks the analyses below it |
| 12.1.5 | Open the account dropdown in the top bar | « Mon espace », then **« Mon voyage »**, then « Déconnexion » (plus « Administration » if you are admin) |
| 12.1.6 | Log out and open `/voyage` directly | Bounced to `/connexion?redirect=/voyage`. You should never see the consent form logged out |

### 12.2 Consent and the age gate

| # | Do | Expect |
|---|---|---|
| 12.2.1 | Open `/voyage` for the first time | Two checkboxes: a consent line about encrypted answers, and « J'ai 15 ans ou plus. » |
| 12.2.2 | Leave both unticked | « Commencer le voyage » is **greyed out and unclickable** |
| 12.2.3 | Tick only the age box | Still greyed out — both are required |
| 12.2.4 | Tick both, click the button | The six session rows appear |
| 12.2.5 | Read the intro | It says in as many words that no session is required and that your analyses work without one |
| 12.2.6 | Check how session 0 is described in that same intro | It « se fait en autonomie » — never « seul » |

### 12.3 Locked sessions

| # | Do | Expect |
|---|---|---|
| 12.3.1 | Look at rows 1 to 5 with no counselor code | Each shows a grey pill reading « Avec un conseiller ». There is **no button at all** — not a greyed-out one |
| 12.3.2 | Enter a valid counselor code, click « Activer » | The code field disappears; the rows now read « Complétez votre profil » if your profile is empty |
| 12.3.3 | Fill prénom + tranche d'âge at `/profil`, return to `/voyage` | Rows 1 to 5 **all** still read « Terminez la session précédente » — session 0 is not finished yet, and that is the order lock working correctly, not a bug |
| 12.3.4 | Enter a wrong or disabled code | "Code invalide ou désactivé." in red. Nothing else changes |
| 12.3.5 | Go to `/voyage/session/4` by typing the URL, with session 3 unfinished | A lock screen: the reason, then the sentence « Cette session n'est pas encore ouverte. », then a remedy button. No questions, no dead « Suivant » |

### 12.4 Session 0 — the 5-minute one

| # | Do | Expect |
|---|---|---|
| 12.4.1 | Click « Commencer » on session 0 | One scrolling list of **20** affirmations, each with a ✓ and a ✗ button. Not one question per screen |
| 12.4.2 | Answer five rows, then reload the page | The five answers are still there — each row saves the moment you press it |
| 12.4.3 | Answer all 20, click « Suivant » | The « Billet de sortie » screen: two free-text boxes, each marked « Facultatif » |
| 12.4.4 | Click « Terminer » with the billet empty | Accepted. Back on `/voyage`, session 0 stamped with a check |
| 12.4.5 | Watch the top of the hub | « Votre phrase » shows a spinner and "Nous la rédigeons. Quelques secondes.", then a single sentence a few seconds later. No page reload needed |
| 12.4.6 | Read that sentence | One sentence about you. No score, no percentage, no psychology or framework word. An age is fine |
| 12.4.7 | Reopen `/voyage/session/0` | It opens read-only on the **20 rows first** (not the billet screen) — greyed out, a banner reading « Session terminée. », and the last screen's button reading « Retour au voyage » |
| 12.4.8 | With code + profile already set, look at row 1 now that session 0 is finished | It offers « Commencer » — session 0 was the last lock blocking it |
| 12.4.9 | Force a failure: in `/admin/prompts`, deactivate "Voyage · phrase (S0)", then finish a fresh session 0 | « Votre phrase » shows "La rédaction de votre phrase n'a pas abouti. Vos réponses sont enregistrées." and a « Réessayer » button |
| 12.4.10 | Reactivate the prompt in `/admin/prompts`, click « Réessayer » | A sentence appears — no error, no jargon |
| 12.4.11 | Leave a phrase on "generating" for more than 3 minutes (or simulate it) | « Votre phrase » switches to "La rédaction de votre phrase prend plus de temps que prévu. Vos réponses sont enregistrées." with a « Réessayer » button |
| 12.4.12 | Try to type more than 1000 characters into a billet de sortie box | The field stops accepting input at 1000 characters |

### 12.5 Sessions 1 to 5 — the player

| # | Do | Expect |
|---|---|---|
| 12.5.1 | Open session 1 | The session's own intro paragraphs, then **one scene per screen** |
| 12.5.2 | Read a scene | A title, a short story, a question, then 6 lettered options (session 1 scene 6 has 8) |
| 12.5.3 | Click « Suivant » without choosing | « Choisissez une réponse pour continuer. » The screen does not advance |
| 12.5.4 | Answer scenes 1 and 2, close the tab mid-scene 3, reopen the session | It lands on **scene 3**, with 1 and 2 already answered |
| 12.5.5 | Answer a scene, click « Suivant », and try to pick a different option before it replies | The options are frozen (disabled) until the save replies — you cannot pick a second answer for the same scene while the first is still saving |
| 12.5.6 | Answer a scene, then turn off your network, then click « Suivant » | An error appears and the screen does not advance. Turn the network back on, click again — it saves and moves on. You lose at most the current scene |
| 12.5.7 | Click « Précédent » | Back one scene, answer still selected. No re-save needed |
| 12.5.8 | Reach the last screen of a session | The session's closing paragraphs, if it has any, then the billet de sortie for that session |
| 12.5.9 | Finish sessions 1 to 5 | After « Terminer » on session 5 the hub shows all six stamped, and a line saying the portrait is awaiting your counselor's validation |
| 12.5.10 | Right after that, look below the six stamps | A card « Lien à transmettre à votre conseiller » with a read-only URL field and a « Copier le lien » button; clicking it briefly shows « Lien copié » |

### 12.6 The portrait

| # | Do | Expect |
|---|---|---|
| 12.6.1 | Open `/voyage/portrait` before the counselor validates | « Votre portrait est rédigé et attend d'être relu avec votre conseiller. Le lien à lui transmettre se trouve sur la page du voyage. » No sections are shown |
| 12.6.2 | Have the counselor validate it, then reload | Six sections in this order: Phrase d'accroche · Qui tu es · Ce qui te fait vibrer · Ce dont tu as besoin · Les chemins possibles · Ce que ton portrait ne dit pas encore |
| 12.6.3 | Read the whole portrait | Prose, tutoiement, **no score, no percentage, no named framework, no "tu es…" verdict, no named métier** |
| 12.6.4 | Click « PDF » | Print preview: an A4 sheet with no top bar and no buttons, long sections flowing onto page 2 |
| 12.6.5 | Go back to `/espace` | The voyage strip now says « Voir mon portrait » |

### 12.7 Erasure

| # | Do | Expect |
|---|---|---|
| 12.7.1 | On `/voyage`, click « Supprimer mon voyage » | A confirmation naming exactly what goes: réponses, phrase, portrait |
| 12.7.2 | Confirm | Back to the consent screen, as if you had never started |
| 12.7.3 | Open `/profil` | **Untouched.** Deleting the voyage must not touch the Profil de base, and deleting the profile must not touch the voyage |

### 12.8 Robustness

| # | Do | Expect |
|---|---|---|
| 12.8.1 | Finish a session, then try to change one of its answers (reopen it, or edit responses from another tab) | The server refuses the write; the row/scene stays inert and reopening the session always shows the read-only banner — nothing you do there is saved |
| 12.8.2 | Stop the backend, then reload `/voyage` | An error message and a « Réessayer » button — **never** the consent form |

> The rule the PM cares about here: **the person never sees a score, a trait
> name, or a framework name.** Not on the hub, not in the phrase, not in the
> portrait. Everything numeric stays on the counselor's side of the wall.
> If a number or a jargon word reaches any of these screens, report it first.

---

## What to report back

For each failure: the step number, the URL, and what you saw instead.

Worth flagging to the PM specifically, whatever the outcome:

1. **The free tier narrowed** — §4 "Ce qui reste à renforcer" moved to paid, per CDC §4. The CGV now says so. That's a contract change and needs their sign-off.
2. **A profile now requires an account.** Neither document says this explicitly; it follows from the persistent-profile decision.
3. **Premium is priced at 24 € by default** — the middle of their "2–3× the paid tier". They should confirm or change it.
4. **The verdict section needs prompt text.** The free tier now asks for it and the schema guarantees the key exists, but no prompt describes what belongs in it yet.
