# Manual test plan — CDC v1.2 / Parcours build

Test environment: http://localhost:8080 (docker dev), or production (see DOCKER.md)

Work through in order. Each row is: what to do → what should happen. Anything
that doesn't match, note the URL and what you saw.

---

## Read this before you start

**One thing will fail until the PM acts, and that's expected — not a bug:**

| What | Why | Symptom |
|---|---|---|
| Free-tier "verdict" quality | The current P1 prompt predates the verdict section | The section will exist and be filled, but the wording may be off — the schema forces the key, the prompt never described what belongs in it |

**The tier of a run is its door's.** The switch that used to force every run to
the paid tier while the PM judged report *content* (`FORCE_ANALYSIS_TIER`) no
longer exists, and nothing the browser sends picks a model. Practical effects:

- A run through « Avec mon compte » or « Sans compte » is the **free tier**:
  §1–§3 and the verdict, lock icons below, and the **willingness-to-pay probe**
  under the report. **§ 4.2** and **§ 7** need such a report.
- A run through « J'ai un code promo » or « J'ai un code conseiller » is
  **Complet**: all 9 sections, no lock icons, and `/debloquer` says
  "Cette analyse est déjà complète" for it.
- To see the paywall and the Premium card (**§ 7.4–7.6**), open a *free* report:
  run one through « Avec mon compte ».
- Each door has its own checks in **§ 8**.

Everything else below should work end to end.

---

## 1 · Entry and navigation

| # | Do | Expect |
|---|---|---|
| 1.1 | Open the landing page | Colours have changed: orange is deeper (`#EA5624`, was a brighter coral), navy is lighter/bluer (`#1C3561`), backgrounds have a faint green tint instead of blue |
| 1.2 | Click any "Lancer mon analyse" / "Démarrer" CTA | Lands on the parcours 1 form **`/analyse/nouveau`** (`/analyse` redirects there since parcours 2 and 3 were retired) |
| 1.3 | Check the landing report preview | Shows §1, §2, §3 only. The locked strip below now starts at **§4** |
| 1.4 | Landing FAQ + pricing card | Say "sections 1 à 3 et le verdict de diagnostic", not "1 à 4" |
| 1.5 | Read the CGV (`/cgv`) | Section 2 says free = sections 1 à 3 + verdict, and lists "les points à renforcer" in the paid offer |
| 1.6 | Try `/analyse/orientation` directly | 404 — the old b1/b2/b3 form is deleted |

---

## 2 · `/analyse`

Parcours 2 and 3 were retired on 2026-10-08; the chooser went with them.

| # | Do | Expect |
|---|---|---|
| 2.1 | Open `/analyse` | Redirected to `/analyse/nouveau` |
| 2.2 | Open `/analyse/direction`, then `/analyse/depart` | The 404 page, both times |

---

## 3 · Mes informations — `/profil`

**You need to be logged in.** Create an account first if needed.

**This page is no longer where answers are given.** Signup asks prénom and
tranche d'âge; the voyage asks the rest (§12.x). `/profil` is where an answer
is re-read, corrected, or erased — nothing in the app sends anyone here to
fill it in.

| # | Do | Expect |
|---|---|---|
| 3.0 | Log out, then open `/profil` directly | Bounced straight to `/connexion?redirect=/profil` — you should never see the form. After logging in you land back on the profile |

### 3.1 Structure

| # | Do | Expect |
|---|---|---|
| 3.1.1 | Open `/profil` | Six **unnumbered** blocks: Vous · Votre situation · Votre parcours · Contraintes pratiques · Conditions de travail · Droits et accord. **No "Votre projet"** — the analysis form asks the same thing as « cible visée » |
| 3.1.2 | Bloc 1 | Prénom, Nom, Ville, **Tranche d'âge — 7 brackets** (14–17 · 18–21 · 22–24 · 25–34 · 35–44 · 45–54 · 55+). **Rayon de recherche is gone**, unless your row already had one — then it shows read-only |
| 3.1.3 | Type a lowercase name | Forces itself to UPPERCASE as you type |
| 3.1.4 | Bloc 2 | Five situations. **There is no separate "type de mobilité" field any more** — the PM merged it in here |
| 3.1.5 | Bloc 2 → pick "En reconversion" | A sub-question appears: rester dans mon domaine / changer de métier / changer de secteur |
| 3.1.6 | Switch away from "En reconversion" | The sub-question disappears and the answer is cleared |
| 3.1.7 | Votre parcours | Dernier diplôme · type d'études · intitulé (facultatif) · études envisagées. Same four the voyage asks between S1 and S2 |
| 3.1.8 | Bloc 4 | Amber warning box: "N'indiquez aucune information de santé, aucun diagnostic, aucun traitement…" |

### 3.2 Bloc 5 — the conditions matrix (this is the biggest new piece)

**Before any of 3.2 saves:** bloc 6 now carries a second tick — « J'accepte que
mes réponses sur mes conditions de travail soient conservées… ». Bloc 5 and the
OETH box are GDPR art. 9 data, and the server refuses to store either without
it. Untick it and save: the matrix is simply not written, and nothing errors.

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
| 4.1 | Signed in, fill a real CV + target, click « Générer mon analyse », choose « Avec mon compte » and « Lancer la version gratuite » | The doors panel opens under the button (the doors themselves are § 8). The analysis runs, then lands on the report |
| 4.2 | Count the sections on a **free** report | **§1, §2, §3 + a "Verdict" section.** §4 is no longer free |
| 4.3 | Check section §3 | Renders as a tag cloud, not paragraphs |
| 4.4 | Check the CTA banner | "Débloquez les **6** sections restantes" (was 5) |

---

## 5–6 · Parcours 2 and 3

Retired on 2026-10-08 (`docs/superpowers/specs/2026-10-08-remove-parcours-2-3-design.md`). The section numbers stay so the references in this plan still hold.

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

## 8 · Les quatre portes

The form at `/analyse/nouveau` is open to everyone, and « Générer mon analyse »
leads to four doors. The server decides each door's tier and who gets the
report (CLAUDE.md, « Les quatre portes »). This replaces the old counselor-view
checks: the `/c/<token>` share link, the « Vue conseiller » tab and the
`VERSION CONSEILLER` badge on the report no longer exist (8.6.4 checks the old
link; the counselor now reads the report on their own page, § 8.4). Everything
here goes through nginx, http://localhost:8080.

**Set up once**

- A verified candidate account, and a second browser profile (or a private
  window) for the rows that say "profile 2".
- An approved counselor account with **three single-use** conseiller codes,
  minted in `/conseiller` with « Places » = 1: the first for 8.1.3 (8.1.4
  tries it again), the second for 8.1.8, which only checks it and spends
  nothing, so 8.2.7 can use it afterwards, and the third for 8.2.4. 8.4 and
  8.7.1 say when to mint more.
- A promo code with **three** uses, minted in `/admin/conseillers`, « Codes
  promo », « Utilisations » = 3: 8.1.6, 8.2.3 and 8.2.6 each spend one (8.2.6
  once you launch after its round trip). A promo code is once per account, so
  each of those three launches is made by an account that has not used it
  yet. A code with no use left answers « Ce code a atteint sa limite
  d'utilisation. » before anything else, at « Continuer » and at the wrong
  door alike: 8.1.6's second try reads « Vous avez déjà utilisé ce code. »,
  and 8.1.8's promo code moves to its door, only while the code still has a
  use left.
- No-login reports: 8.1.2 makes the first (8.5.1 keeps it), 8.2.8 makes
  another (8.5.3 opens it, 8.5.4 deletes it) and 8.5.2 asks for a new one.
  Print one (8.5.5) before 8.5.4 deletes it, or make one more.
- Locally there is no Resend key, so a mail is a line in
  `docker compose logs backend`, and so are the verification and sign-in links
  (`DEV — no RESEND_API_KEY, link for <address>: <link>`).
- A free-tier run costs about 0.06 $ and a Complet run about 0.2 $. Where a row
  only needs a finished report to look at, reuse one.

### 8.1 Each door, signed out

Open `/analyse/nouveau` with no session. Paste a CV of at least 200 characters
and a target of at least 50.

| # | Do | Expect |
|---|---|---|
| 8.1.1 | Click « Générer mon analyse » | Nothing starts. A panel « Comment voulez-vous continuer ? » opens under the button with four doors, in this order: « Avec mon compte », « J'ai un code conseiller », « J'ai un code promo », « Sans compte ». One door is open at a time |
| 8.1.2 | « Sans compte »: tick « J’accepte les CGV et la politique de confidentialité. », click « Lancer sans compte » | The address becomes `/rapport#<long key>`: the waiting screen, then the free report (§1–§3 + verdict). The bar above it reads « Ce rapport n'est accessible que par ce lien, jusqu'au <date, 30 days ahead>. » with « Copier le lien », « Créer un compte pour le garder », « PDF » and « Supprimer ce rapport ». The waiting screen promises no mail: « Le rapport s’affiche ici automatiquement. Gardez ce lien pour le retrouver. » |
| 8.1.3 | « J'ai un code conseiller »: prénom, nom, the single-use code, tick the box, click « Envoyer à mon conseiller » | The notice « Le rapport complet sera envoyé à votre conseiller, pas à vous : vous n'en recevrez pas de copie. Votre conseiller pourra vous le présenter ou vous le transmettre. » sits above the box. After the click you are on `/analyse/envoyee`: « C’est envoyé. », with no link, no id and no report text anywhere |
| 8.1.4 | Use the same code at the same door again | Refused inside the panel: « Ce code a atteint sa limite d'utilisation. » (The same code's voyage use is counted apart, and is still free.) |
| 8.1.5 | « J'ai un code promo »: type the promo code, click « Continuer » | Taken to `/inscription` (sign up first). Sign in (a new account needs its verification link first, in the backend log): you come back on `/analyse/nouveau` with the form refilled and the panel open at « J'ai un code promo ». Nothing has started |
| 8.1.6 | Click « Lancer l’analyse complète » (the code is pre-filled in the same browser for two hours; otherwise retype it) | The waiting screen, then a report with all 9 sections and no unlock offer. Use the same code again with the same account: « Vous avez déjà utilisé ce code. » |
| 8.1.7 | Start again. « Avec mon compte »: click « Créer un compte ou me connecter » | The same round trip as 8.1.5, back on the form with the panel open at « Avec mon compte ». « Lancer la version gratuite » runs the free tier, and the report is saved in `/espace` |
| 8.1.8 | Type a conseiller code at « J'ai un code promo » and click « Continuer » | The panel moves to « J'ai un code conseiller » with the code kept in its field, and shows « Ce code est un code conseiller : choisissez « J'ai un code conseiller ». » A promo code typed at the advisor door moves the other way, with « Ce code est un code promo : choisissez « J'ai un code promo ». » |

### 8.2 Each door, signed in; an expired session

| # | Do | Expect |
|---|---|---|
| 8.2.1 | Signed in, open the form and click « Générer mon analyse » | Three doors: « Sans compte » is hidden, since « Avec mon compte » gives the same tier and keeps the report |
| 8.2.2 | « Avec mon compte » → « Lancer la version gratuite » (skip if 8.1.7 just did it) | A free report, saved in `/espace` |
| 8.2.3 | « J'ai un code promo » with a promo code this account has not used (a second code, or the code of 8.1.6 from a second account) → « Lancer l’analyse complète » | A Complet report in `/espace` |
| 8.2.4 | « J'ai un code conseiller » as a signed-in candidate | Behaves exactly as signed out (8.1.3): the report goes to the counselor, and nothing new appears in the candidate's `/espace` |
| 8.2.5 | Signed in, on the form: make the access cookie expire. Wait past `JWT_ACCESS_TOKEN_EXPIRES` (1 h), or replace `access_token_cookie` with an expired token in the browser's cookie editor (keep one expired token to paste back for the next rows). **Do not reload.** Click « Enregistrer le brouillon » | « Votre session a expiré : ce brouillon est gardé dans ce navigateur. Connectez-vous pour l’enregistrer dans votre espace. » instead of « Brouillon enregistré » |
| 8.2.6 | Cookie expired as in 8.2.5, form not reloaded: click « Générer mon analyse », choose « Avec mon compte » and click « Lancer la version gratuite » (then, separately, the same with « J'ai un code promo » and a valid code) | The server answers 401 and the panel sends you through the sign-in round trip **once**, to `/inscription`: no loop. After signing in you are back on the form with the panel open at that door |
| 8.2.7 | Cookie expired as in 8.2.5, form not reloaded: « J'ai un code conseiller » with a code that has a free place | It works as in 8.1.3: the advisor door ignores the session |
| 8.2.8 | Cookie expired, then reload the form | You are a signed-out visitor: four doors, and « Sans compte » works |

### 8.3 Signing in mid-flow

| # | Do | Expect |
|---|---|---|
| 8.3.1 | In profile 1, fill the form, choose « Avec mon compte » → « Créer un compte ou me connecter » and sign up with a new address and password. Take the verification link from the backend log, open it in **profile 2** and enter the signup password | Signed in on profile 2, on `/analyse/nouveau`, with the form refilled from what profile 1 held and the panel open at « Avec mon compte ». Nothing has started |
| 8.3.2 | Same start, but on the sign-in page ask for « Recevoir un lien de connexion » with an existing account that has **no draft**. Open the link in profile 2 and click « Continuer » | Signed in on profile 2 with an empty form and the sentence « Votre formulaire est resté sur l’appareil où vous l’avez rempli : connectez-vous depuis celui-ci pour le retrouver. » The draft stayed in profile 1 |
| 8.3.3 | Only if `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` are set locally: same start, « Continuer avec Google », in the same browser | Back on the form, refilled, the panel open at « Avec mon compte ». Without both keys the button does not show: skip this row and say so |

### 8.4 The counselor's side

Use the advisor run of 8.1.3, or mint another single-use code and make a new one.

| # | Do | Expect |
|---|---|---|
| 8.4.1 | When the advisor run ends, read `docker compose logs backend` | A line `RESEND_API_KEY missing — mail to <the counselor's address> not sent.` That is the mail « Une analyse est prête », for the counselor and nobody else: the candidate gets none |
| 8.4.2 | Sign in as the counselor and open `/conseiller` | « Mes bénéficiaires » lists the person as prénom + nom, with « Voir l’analyse » in the « Analyse » column. The code's row shows « 1 analyse · 0 voyage » beside its status, and no « Révoquer » (a code that has been used cannot be revoked) |
| 8.4.3 | Click « Voir l’analyse » | `/conseiller/analyses/<id>`, headed « Prénom NOM · code « <label> » · <date> ». While the run goes: « Analyse en cours… La page se met à jour toute seule. » Then the complete report, 9 sections, with no unlock offer and no price probe |
| 8.4.4 | Click « PDF » | A print preview of the report alone: no top bar, no buttons, no « Notes privées » |
| 8.4.5 | Type in « Notes privées », click « Enregistrer », reload | « Enregistré. », and the note is back after the reload. Another counselor opening the same URL sees « Analyse introuvable. » |
| 8.4.6 | As any signed-in user, and signed out, open `/api/analyses/<id>` with the id from the URL above | `403` « Accès non autorisé. » both times: an advisor report is never served on a candidate route |
| 8.4.7 | Make the run fail: `UPDATE analyses SET status = 'error' WHERE id = '<id>';` (mysql command in § 8.7), then reload the page | « L’analyse n’a pas abouti. Vous pouvez la relancer. » and a « Relancer » button. Click it: the same row runs again (a real Complet run), the page goes back to « Analyse en cours… » and ends on the report. The code still counts 1 analyse |
| 8.4.8 | Click « Supprimer l’analyse » | An in-page question « Supprimer définitivement cette analyse ? » with « Supprimer » and « Annuler » — never a browser dialog. « Supprimer » returns to `/conseiller`: the report and its note are gone, the code still counts its use |

### 8.5 Keeping a no-login report

| # | Do | Expect |
|---|---|---|
| 8.5.1 | On the report of 8.1.2 click « Créer un compte pour le garder » and sign in to an **existing** account | `/espace?garder=1`: « Le rapport est maintenant dans votre espace. » and the report comes first in the list. The old `/rapport#…` link now says « Ce lien n'est plus valide. » |
| 8.5.2 | Repeat with a new no-login report and a **password signup**; open the verification link and enter the password | The report is in `/espace`, with no sentence: the verification link attached it. The old link is dead too |
| 8.5.3 | While signed in, open a still-valid `/rapport#…` link | The button reads « Garder dans mon espace » and goes straight to `/espace`. The offer « Créez un compte pour débloquer le rapport complet » is not shown |
| 8.5.4 | On a no-login report click « Supprimer ce rapport », then « Supprimer » | « Supprimer définitivement ce rapport ? » first, in the page, then « Rapport supprimé. » with « Nouvelle analyse ». The link is dead |
| 8.5.5 | **A real print, by hand, on four browsers.** On a no-login report in Chrome press Ctrl/Cmd+P with « Headers and footers » ticked; repeat once in Safari on a Mac, once in Chrome on Android and once in Safari on iOS (each phone's own Share → Print) | Where the browser prints the address (header or footer), it has no `#…`: the page removes the key for the print and puts it back afterwards. Close the print screen: the address bar has its `#<key>` again, or at the latest after one tap or key press on the page (a browser that never says the print is over). On iOS 15.6 and 16 Safari may say so before its print screen closes (WebKit bug 245171), so the key could come back in time to be printed: on the iPhone, read the printed address itself |

### 8.6 Limits, logs and retired pages

Commands for this section:

```bash
# 8.6.1: sixty POSTs the server refuses before any run starts (no cost)
for i in $(seq 1 60); do curl -s -o /dev/null -w '%{http_code} ' -X POST http://localhost:8080/api/analyses/ -H 'Content-Type: application/json' -d '{"door":"anonymous"}'; done; echo

# 8.6.3: a probe in the query string and in the Referer, then look for it
curl -s -o /dev/null 'http://localhost:8080/api/health?probe=PROBE123' -H 'Referer: http://localhost:8080/x?probe=PROBE123'
docker compose logs nginx | grep -c PROBE123
docker compose logs nginx | tail -3
```

| # | Do | Expect |
|---|---|---|
| 8.6.1 | Run the burst command | About 41 `400` (the empty form is refused) and then `429` from nginx, once the burst of 40 is used |
| 8.6.2 | Within a few seconds of the burst, use a door in the UI with a valid form (« Sans compte », box ticked, « Lancer sans compte ») | The panel shows « Trop de tentatives — réessayez dans une minute. » and no run starts |
| 8.6.3 | Run the probe commands | `0` for the count. The last lines have the shape `<address> [<time>] "GET /api/health" <status> <bytes> <seconds>`: nothing after the path, no Referer. Locally this covers nginx only: the dev backend (`flask run`) logs query strings, and the gunicorn format ships with the production image (check it on the VPS: DOCKER.md, « Access logs record the path only ») |
| 8.6.4 | Open `/c/anything` | The static page « Ce lien n’est plus actif. » with « Retour à l’accueil ». `curl -i http://localhost:8080/api/c/anything` answers 404 |
| 8.6.5 | `docker compose exec backend flask purge-expired --dry-run` | Four counts — `held_drafts`, `anonymous`, `advisor`, `run_log` — then `dry run — nothing deleted` |

### 8.7 On real MySQL

The two checks SQLite cannot reproduce. The local database:
`docker compose exec db mysql -uroot -pneoori_dev neoori`.

```bash
# 8.7.1: put the single-use code in <CODE>, then ten advisor submits at once
BODY='{"door":"advisor","code":"<CODE>","prenom":"Test","nom":"Course","consent":true,"inputs":{"cv_text":"'"$(printf 'c%.0s' $(seq 1 300))"'","cible_visee":"Chauffeur livreur PL dans une entreprise de transport régional"}}'
seq 1 10 | xargs -P 10 -I{} curl -s -o /dev/null -w "%{http_code}\n" \
  -X POST http://localhost:8080/api/analyses/ -H 'Content-Type: application/json' -d "$BODY" | sort | uniq -c
```

| # | Do | Expect |
|---|---|---|
| 8.7.1 | The race. Mint a single-use code for the test counselor (`/conseiller`, « Places » = 1), run the command above, then count in MySQL: `SELECT COUNT(*) FROM code_redemptions WHERE code_id = '<id of that code>';` | Exactly one `201`; the other nine `400` (« Ce code a atteint sa limite d'utilisation. ») or `409`. The count is `1`. Ten requests fit the `analyses` burst of 40, and only the one run costs anything |
| 8.7.2 | A run a restart orphaned. Take an advisor report and make it look stuck: `UPDATE analyses SET status = 'running', started_at = UTC_TIMESTAMP() - INTERVAL 20 MINUTE WHERE id = '<id>';` then open `/conseiller/analyses/<id>` | « L’analyse n’a pas abouti. Vous pouvez la relancer. » with « Relancer », and the row is now `error` in MySQL. Use `UTC_TIMESTAMP()`, not `NOW()`: the app writes UTC. A row started less than 15 minutes ago stays `running`, and a `queued` row is never touched |

---

## 9 · Admin — `/admin`

| # | Do | Expect |
|---|---|---|
| 9.1 | `/admin/prompts` | The selector shows **three** prompts, in this order: Parcours 1 · J'ai une cible / Voyage · phrase (S0) / Voyage · portrait |
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

**You need to be logged in.** Sessions 1 to 5 need a counselor code. Sessions 2
to 5 also need « Ton parcours », and session 5 needs the conditions step — each
is asked *inside* the voyage, and a locked card links straight to the step that
opens it. Those are gates, not bugs; none of them sends you to `/profil`.

Text that comes from the paper cahier — session titles, scenes, the portrait —
says *tu* wherever it appears. Everything the app adds — buttons, cards,
banners, error messages — says *vous*.

### 12.1 Entry points

| # | Do | Expect |
|---|---|---|
| 12.1.1 | Open the landing page and scroll past the hero | A navy band, eyebrow "Le voyage", heading « Avant de parler de poste, parlons de vous. » |
| 12.1.2 | Click « Commencer le voyage » while logged out | `/connexion?redirect=/voyage`, and after logging in you land on `/voyage` |
| 12.1.3 | Open `/analyse` | Redirected to the parcours 1 form; the voyage is reached from the landing, `/espace` and the account menu |
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
| 12.4.1 | Click « Commencer » on session 0 | One scrolling list of **20** affirmations, each with three buttons: ✓, – (neutre) and ✗. Not one question per screen |
| 12.4.2 | Answer five rows, then reload the page | The five answers are still there — each row saves the moment you press it |
| 12.4.3 | Answer all 20 | The button at the bottom reads « Terminer » — there is no « Billet de sortie » screen any more |
| 12.4.4 | Click « Terminer » | Back on `/voyage`, session 0 stamped with a check |
| 12.4.5 | Watch the top of the hub | « Votre phrase » shows a spinner and "Nous la rédigeons. Quelques secondes.", then a single sentence a few seconds later. No page reload needed |
| 12.4.6 | Read that sentence | One sentence about you. No score, no percentage, no psychology or framework word. An age is fine |
| 12.4.7 | Reopen `/voyage/session/0` | It opens read-only on the **20 rows** — greyed out, a banner reading « Session terminée. », and the button reading « Retour au voyage » |
| 12.4.8 | With code + profile already set, look at row 1 now that session 0 is finished | It offers « Commencer » — session 0 was the last lock blocking it |
| 12.4.9 | **Local stack only — never do this against the production prompt.** Stop the backend, set an invalid `ANTHROPIC_API_KEY` in the local env, start the backend, then finish a fresh session 0 | « Votre phrase » shows « La rédaction de votre phrase n'a pas abouti. Vos réponses sont enregistrées. » and a « Réessayer » button |
| 12.4.10 | Restore the real key, restart the backend, click « Réessayer » | A sentence appears — no error, no jargon |
| 12.4.11 | Leave a phrase on "generating" for more than 3 minutes (or simulate it) | « Votre phrase » switches to "La rédaction de votre phrase prend plus de temps que prévu. Vos réponses sont enregistrées." with a « Réessayer » button |
| 12.4.12 | Mark five rows « – », then try a sixth | The other rows' « – » buttons are greyed out and « 5 réponses neutres maximum : retirez-en une pour en choisir une autre. » shows above the list. Switching one « – » to ✓ frees a slot |

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
| 12.5.8 | Reach the end of a session | Sessions 1 and 5: « Suivant » on the last scene opens a closing screen with the session's last paragraphs and « Terminer ». Sessions 2, 3 and 4: the last scene's own button reads « Terminer ». No « Billet de sortie » anywhere |
| 12.5.9 | Finish sessions 1 to 5 | After « Terminer » on session 5 the hub shows all six stamped and « Votre portrait est en cours de rédaction. » while it is being written, then « Votre portrait est rédigé. Transmettez le lien ci-dessus à votre conseiller : vous y aurez accès une fois qu'il aura été relu avec vous. » once it is |
| 12.5.10 | Right after that, look below the six stamps | A card « Lien à transmettre à votre conseiller » with a read-only URL field and a « Copier le lien » button; clicking it briefly shows « Lien copié » |
| 12.5.11 | On a scene, tap three options, then a fourth, then tap the first one again | Badges « 1er choix », « 2e choix », « 3e choix » in tap order; the other options grey out at three; tapping the first removes it and the other two move up to « 1er » and « 2e » |

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
| 12.8.1 | Finish a session, then try to change one of its answers by reopening it | The server refuses the write; the session opens read-only with the « Session terminée. » banner and inert rows/scene — nothing you do there is saved |
| 12.8.2 | Instead, leave a session open in this tab and finish it from another tab, then change an answer here | The row/scene shows the new value on screen along with « Cette session est terminée : ses réponses ne sont plus modifiables. », but nothing is saved — reopening the session (or reloading) shows it read-only |
| 12.8.3 | Log in, open `/espace`, stop the backend, then open « Mon voyage » from the account menu **without reloading** | « Connexion au serveur impossible. Il démarre peut-être — réessayez dans 30 secondes. » plus a « Réessayer » button — **never** the consent form |

### 12.9 Ce que le voyage change dans une analyse

Run these analyses through « Avec mon compte » or « J'ai un code promo »: the
advisor and no-login doors fold in no profile and no voyage (§ 8), so
`inputs` never carries a `_voyage` line there.

| # | Do | Expect |
|---|---|---|
| 12.9.1 | With an account that has no voyage, run an analysis and open its response (`GET /api/analyses/<id>`) in the Network tab (F12 → Network) | Runs and completes exactly as before. `inputs` has **no** `_voyage` key and **no** `_voyage_id` key at all; `voyage_id` is `null`. The voyage is never required |
| 12.9.2 | Play session 0 to the end, wait for the phrase, then run a new analysis and look at `inputs._voyage` in the same response | A list of **exactly 2** lines: « Phrase révélée : … » and « Ce qui l'attire le plus dans dix ans : … ». `inputs._voyage_id` and the top-level `voyage_id` are the same id |
| 12.9.3 | Have the counselor validate the portrait (§ 13.22), then run **another** new analysis and look at `inputs._voyage` | Up to **9** lines — the two from § 12.9.2 plus « Univers dominants », « Besoin dominant », « Ambivalences relevées », « Cadre où elle donne le meilleur », « Ce qui l'épuise », « Ce qui la met en colère », « Se sent vivant(e) quand » (a line is omitted, not left empty, when it has nothing to say). The § 12.9.2 analysis itself is untouched — still its own 2 lines |
| 12.9.4 | Read every line in `inputs._voyage` carefully | The first line (« Phrase révélée : … ») is free text the model wrote from the person's own answers and may legitimately carry a digit — an age or a duration, e.g. a made-up « Après 17 ans d'usine… », is not a bug. **Every other line must never contain a digit**, and no line may contain a framework word: « score », « névrotisme », « RIASEC », « Big Five », « extraversion », « conscienciosité », « Élevé » / « Moyen » / « Faible ». If one does, stop and report it — it is the one bug in this section that matters |
| 12.9.5 | On an analysis carrying a voyage, open the report itself, and print it to PDF | The voyage lines are rendered on **neither** the page nor the printout — they exist only in the raw `inputs` payload read directly, as in the rows above. Model-facing only, never on a page. (The old « Vue conseiller » tab and the `/c/<token>` share link are gone; 8.6.4 checks the link.) |
| 12.9.6 | With that same analysis still around, open `/voyage`, click « Supprimer mon voyage » (§ 12.7.1) and confirm, then re-open the analysis's response | `inputs` no longer has `_voyage` or `_voyage_id`, and the top-level `voyage_id` is `null`. The analysis and its delivered report text are untouched — only the copied voyage lines are gone |

> The rule the PM cares about here: **the person never sees a score, a trait
> name, or a framework name.** Not on the hub, not in the phrase, not in the
> portrait. Everything numeric stays on the counselor's side of the wall.
> If a number or a jargon word reaches any of these screens, report it first.

---

## 13 · Le voyage — vue conseiller

Prerequisites: one candidate account that has finished the five sessions (its
voyage row is `termine` with `portrait_status` = `draft`) and its `share_token`;
one second account to promote; one admin account. A few rows below call for a
second, ad hoc fixture — an `error` portrait, a failed phrase, a stale
`scoring_version`, a broken connection — each row says how to get there.

| # | Do | Expect |
|---|---|---|
| 13.1 | Logged out, open `/voyage/c/<token>` | Redirected to `/connexion?redirect=/voyage/c/<token>`. The fiche never renders |
| 13.2 | Log in as the **candidate who played**, open `/voyage/c/<token>` | A card saying « Accès non autorisé. » — no numbers, no trait names, no portrait text anywhere on the page. Open the network tab: no request to `/api/voyage/c/...` was made |
| 13.3 | As admin, open `/admin/utilisateurs`, set the second account's role select to « conseiller » | The select shows « conseiller » straight away, no page reload, no error under the row |
| 13.4 | Still in `/admin/utilisateurs`, try to set the **only** admin account to « candidat » | The row shows « Impossible de retirer le dernier rôle administrateur. » and the select goes back to « administrateur » on reload |
| 13.5 | Log in as the new conseiller. Stop the backend (or otherwise break the connection), then open `/voyage/c/<token>` | The load fails: an error card with a « Réessayer » button — never a dead end. Restart the backend and click « Réessayer »: the fiche loads normally |
| 13.6 | Log in as the new conseiller, open `/voyage/c/<token>` | The fiche renders: navy band, badge « VERSION CONSEILLER », title « Le voyage · <prénom> », then the warning strip « Document conseiller… » |
| 13.7 | Read the top of the sheet, above the synthesis table | The legend « Les blocs bordés de pêche sont rédigés par l'IA. La phrase a déjà été montrée à la personne, sans relecture préalable. Le portrait est un brouillon : il ne lui parvient qu'une fois que vous l'avez validé. ». The peach-bordered blocks it names are the phrase block just below it and, further down, the six portrait fields |
| 13.8 | Read the peach-bordered phrase block | The marker « Déjà affichée à la personne » above the sentence. On a voyage whose session-0 phrase failed to generate, the block reads « La phrase n'a pas pu être rédigée. »; while it is still being written, « Phrase en cours de rédaction. »; before generation has even started, « Phrase pas encore rédigée. » — never an empty tint |
| 13.9 | Open the fiche for a voyage scored under a retired bank version (locally: set the row's `scoring_version` DB column below `bank.SCORING_VERSION`, then reload) | Above the tableau de synthèse: « Ces réponses ont été enregistrées avec une version antérieure du questionnaire ; certaines sections peuvent apparaître incomplètes. » A voyage scored at the current version shows no such warning |
| 13.10 | Read the key-facts strip | Prénom, tranche d'âge and situation are in French words (« 25 – 34 ans », « En recherche d'emploi »), not `25_34` / `en_recherche` |
| 13.11 | Read « Tableau de synthèse — Toutes dimensions » | Eleven rows, from « Axes bipolaires (S0) » to « Sens — Moment vivant », each with a session and a result |
| 13.12 | Read « Profil RIASEC — Barres de visualisation » | Six bars, R I A S E C in that order, each labelled `n / max`. The maxima read **R 12 · I 11 · A 10 · S 10 · E 11 · C 9** — not 10/10 for E and C. The top three are orange |
| 13.13 | Read « Axes bipolaires — Session 0 » | Ten rows A1…A10, each with its French name, its two poles, its ✓/✗ counts and its resultant. Only rows with a « tension » badge are between −2 and +2 — and **A1 never carries one** |
| 13.14 | Read « Tensions S0 — Ambivalences à explorer » | The ×1.5 note, then one card per tension with the question « J'ai noté une ambivalence sur … » |
| 13.15 | Read the four session boxes | « Synthèse — Besoins SDT dominants » with three counters, « Synthèse Big Five — Profil cognitif » with five Élevé/Moyen/Faible cells, « Synthèse environnementale » with six lines, « Synthèse Risque & Sens » with seven |
| 13.16 | Scroll to « Restitution » | The wording rappel table, then PHASE 01 to PHASE 05 with their durations (5/10/10/10/5 min), then « Phrases utiles en restitution » with five quotes |
| 13.17 | Edit « Phrase d'accroche », click « Enregistrer » | Button flips to « Enregistré » with a green check. Reload the page: the edit is still there and the status line now says « · modifié par un conseiller » |
| 13.18 | Empty one textarea, click « Enregistrer » | An inline red line « À compléter avant d’enregistrer : <section>. » — nothing is sent to the server |
| 13.19 | Local stack only — never against the production prompt. Stop the backend, set an invalid `ANTHROPIC_API_KEY`, restart, then click « Régénérer » on a draft portrait; once it lands on `error`, reload the fiche | Under the status line « Échec de la rédaction », the failure reason (`portrait.error`) in red — and « Régénérer » is still offered, never a dead end. Restore the key, restart the backend and click it again: a fresh draft replaces it |
| 13.20 | Click « Régénérer », then « Confirmer : réécrire le brouillon » | The editor is replaced by « Rédaction en cours. Cette page se met à jour toute seule. » and, within a few seconds and with no reload, a new draft fills the six fields |
| 13.21 | If the red banner « Vocabulaire à vérifier » appears | Read the draft: it should be the reason — a test name, a trait name or the word « score » survived into the prose. Rewrite that passage before validating |
| 13.22 | Click « Valider et transmettre » | Status becomes « Validé et transmis · validé le <date> ». « Régénérer » and « Valider » disappear; « Enregistrer » stays |
| 13.23 | Log back in as the candidate, open `/voyage/portrait` | The six sections are there — the same text the conseiller validated, and nothing else from the fiche |
| 13.24 | Back on the fiche, click « Régénérer » again and confirm, then edit one field (e.g. « Qui tu es ») **without** clicking « Enregistrer », then click « Valider et transmettre » directly | Your edit is saved first and only then transmitted. Log back in as the candidate: the field shows your edited wording, not the regenerated draft — before this fix, validate sent the stored, un-edited text and the correction was silently lost |
| 13.25 | Back on the fiche, type in « Mes notes de restitution », click « Enregistrer », reload | The note comes back. Log in as a *different* conseiller and open the same fiche: the note field is empty (notes are per conseiller) |
| 13.26 | Click « PDF fiche » | The print preview shows the synthesis sheet, the portrait as prose (not as textareas) and the restitution guide. It does **not** show the action bar, the buttons or the notes |
| 13.27 | `/admin` overview | A « Le voyage » row of four tiles: Voyages commencés / Session 0 terminée / Voyages terminés / Portraits validés, with the counts you would expect from the rows you created |

---

## What to report back

For each failure: the step number, the URL, and what you saw instead.

Worth flagging to the PM specifically, whatever the outcome:

1. **The free tier narrowed** — §4 "Ce qui reste à renforcer" moved to paid, per CDC §4. The CGV now says so. That's a contract change and needs their sign-off.
2. **A profile now requires an account.** Neither document says this explicitly; it follows from the persistent-profile decision.
3. **Premium is priced at 24 € by default** — the middle of their "2–3× the paid tier". They should confirm or change it.
4. **The verdict section needs prompt text.** The free tier now asks for it and the schema guarantees the key exists, but no prompt describes what belongs in it yet.


### 3.4 Erasure — « Supprimer mes informations »

New. `DELETE /api/profile` had existed since the profile shipped with nothing
in the app calling it: a profile could be read and corrected but never erased
(RGPD art. 17).

| # | Do | Expect |
|---|---|---|
| 3.4.1 | Scroll to the bottom of `/profil` | A card outside the form, red-ringed, saying what goes and what stays |
| 3.4.2 | Click « Supprimer mes informations » | A browser confirm. Cancel it — nothing happens |
| 3.4.3 | Confirm it | Every field blanks, including both consent ticks. No redirect |
| 3.4.4 | Reload | Still empty — `GET /api/profile` returns `{"profile": null}` |
| 3.4.5 | Open `/voyage` | Sessions 1 to 5 are locked on « Complétez votre profil », linking to `/voyage/etape/entree`. **Your voyage answers, phrase and portrait are untouched** |
| 3.4.6 | Open a report you already generated | Unchanged. Erasing the profile does not rewrite a report already delivered |

### 3.5 What the steps write, and where

| # | Do | Expect |
|---|---|---|
| 3.5.1 | Sign up with a prénom and a bracket | `/profil` already shows both — signup seeds them |
| 3.5.2 | Open `/voyage` with no voyage yet | The gate asks prénom, tranche d'âge, ville, nom (facultatif) and situation before « Commencer le voyage » |
| 3.5.3 | Finish S1, open S2 | Locked on « Complétez votre parcours ». The chip is a link, not dead text |
| 3.5.4 | Click it | `/voyage/etape/parcours` — the four questions, then back to the voyage with S2 open |
| 3.5.5 | Finish S4, open S5 | Locked on « Complétez vos conditions de travail » → `/voyage/etape/conditions`: contraintes pratiques, the eight-family matrix, the OETH box, the art. 9 tick |
| 3.5.6 | Leave the whole conditions step empty, tick only the consent, continue | Accepted. Bloc 5 is optional for everyone — what the gate asks is that the step was *seen* |
| 3.5.7 | Enter a counselor code on the hub | The card updates **without a reload** |
