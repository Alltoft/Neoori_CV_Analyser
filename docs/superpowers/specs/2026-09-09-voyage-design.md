# Le voyage — Design Spec
Date: 2026-09-09
Status: proposed — developer decisions marked ⚑ are defaults, override any of them

## Overview

Digitise the two PM documents `neoori_cahier_papier.pdf` (student workbook, 6 sessions S0–S5) and `neoori_scoring_restitution-1.pdf` (counselor scoring + restitution manual) as **le voyage** — the module the Parcours doc §7 describes and CLAUDE.md / plan.md had parked as "Portrait module, out of scope".

PM ruling (2026-09-09, relayed by the developer):

1. The voyage is the **general entry card**, not a replacement for parcours 3.
2. Playing it requires an account; its results are saved on the person's profile.
3. Those results feed **every later analysis** (P1/P2/P3) as additional context.
4. **Session 0 (5 min) is self-serve.** Sessions 1–5 (the complete game) require a counselor.

Everything the two PDFs contain is implemented: the 53 scored items, the exit tickets, the scoring tables for all five frameworks, the synthesis sheet, the six-section portrait template with its wording rules, and the 5-phase restitution guide.

This settles Parcours doc §11's open question "le parcours est-il offert ou vendu à part ?" for launch: **offered**. S0 is free for everyone; S1–S5 are unlocked by a counselor code, which is already the free-access mechanism for Cap Emploi / Mission Locale / France Travail beneficiaries. If it is sold later, the gate moves from code to payment at one place (`POST /api/voyage/unlock`), exactly like `unlock_analysis`.

---

## Decisions

| # | Decision | Why |
|---|---|---|
| 1 | Name: **le voyage** (Parcours doc §7). Route `/voyage`, tables `voyages`, `voyage_notes`. | PM's own vocabulary; the cahier's title ("Mon cahier d'exploration") is used as the on-screen subtitle. |
| 2 ⚑ | The **cahier is the canonical question bank**. Parcours doc §7's Jules Verne tour (17 questions, escales, passport stamps) and the Académie des Ori variant are **skins for later**, not v1. Session structure, billet de sortie and permanent progress bar — which both documents share — are in v1. | The cahier is newer (Sept vs July), more detailed, and paper-tested. The bank is data-driven, so a skin changes presentation, not scoring. |
| 3 | New models, **not** `Analysis` rows. One `Voyage` per attempt, many per user, at most one *open* (`en_cours` / `s0_termine`). A retake = `POST` once the previous one is `termine`; the old row is kept because analyses reference it. Abandoning mid-way = `DELETE` (erase). | Multi-session, weeks-long, counselor-gated lifecycle — nothing like a one-shot analysis. Many-per-user gives retake + traceability (an analysis records which voyage fed it). |
| 4 | **Everything content-bearing is encrypted at rest** with the existing Fernet util: answers, computed scores, micro-portrait, portrait. Plaintext columns hold only status, timestamps and FKs. | A psychometric profile (neuroticism, fear of judgment, what someone would sacrifice) is more sensitive than bloc 5. Same guarantee: never in `to_dict()`, never in a log, never in a PDF of an analysis. |
| 5 | **Scoring is arithmetic in Python**, pure functions, no model. Scores are **recomputed from answers on read**, never stored separately; the portrait stores a snapshot of the synthesis it was written from. | No API cost, deterministic, unit-testable. Not storing scores avoids stale rows when a scoring table is corrected; the snapshot keeps traceability. |
| 6 | **Scoring weights never leave the server.** `GET /api/voyage/bank` serves text only. | The counselor manual is marked confidential; the option→trait mapping is the product. |
| 7 | **The person never sees a score, a trait name, or a framework name.** Candidate sees: the S0 phrase, the six-section portrait prose. The counselor sees the synthesis sheet. | Cahier p2 wording rules (« jamais "score" », « jamais "faible" »). Enforced in code (`prompt_context()`, response shapes), not only in the prompt. |
| 8 | Two LLM calls, both prompt-slot-managed in `/admin/prompts`: **`voyage_micro`** (one sentence after S0, free-tier model, ~200 tokens) and **`voyage_portrait`** (six sections after S5, paid-tier model, ~3000 tokens, JSON-schema structured output). | Same PromptVersion / traceability regime as analyses; PM edits wording without a deploy. |
| 9 | **Counselor gate = counselor code + validation.** A code (existing `CounselorCode`) unlocks S1–S5. After S5 the app drafts the portrait; a logged-in `counselor`/`admin` opens `/voyage/c/<token>`, sees the synthesis sheet, edits the draft, and **validates**. The candidate sees the portrait only once validated. | "Counselor mandatory" without requiring the counselor to sit through 90 minutes of answering. The human step the paper protocol protects — restitution — stays human. |
| 10 | **Injection into analyses** follows the bloc 5 precedent: `_merge_profile()` reduces the voyage to 6–8 plain-French lines stored as `inputs["_voyage"]`, plus `Analysis.voyage_id`. S0-only → the phrase + top-3 attractions. Full block → **only once the portrait is validated**. | Before validation, an analysis must not tell the person what the counselor hasn't restituted yet. Reduction at merge time keeps unlock-regeneration consistent, like `_conditions`. |
| 11 | **Never required.** Every parcours runs identically with no voyage; the block is simply absent. | `depart/page.tsx:22-24` — parcours 3 exists to remove barriers. |
| 12 ⚑ | **Sessions in order** (S(n) needs S(n−1)). S0 needs account + voyage consent. S1 additionally needs the code **and** a Profil de base with at least prénom + tranche d'âge. | The portrait uses prénom / age / situation; asking again would break « une information, une seule fois ». Profil is *not* required for the 5-minute S0. |
| 13 ⚑ | **Consent line + age attestation** before S0: a dedicated checkbox (encrypted answers, erasable any time) and « J'ai 15 ans ou plus ». Under-15 (parental consent) is **out of scope** for v1. | Psychometric data needs its own consent record. 15 is the French digital-consent age (LIL art. 45). The cahier's *Classe* field suggests younger users exist — flagged for the PM/legal. |
| 14 | **Erasure is independent**: `DELETE /api/voyage` drops the voyage and its notes; profile erasure is untouched, and vice-versa. | The two-speed storage argument to prescribers: « vous gardez le contrôle de ce qu'on garde ». |
| 15 ⚑ | **Tone**: the cahier's text (tutoiement) is reproduced **verbatim** inside the sessions and the portrait. App chrome around it (landing card, hub, buttons, counselor UI) stays vouvoiement, sober, CLAUDE.md ban list applies. | The cahier is PM-authored, paper-tested content; rewriting 53 items to *vous* is the PM's call, not the developer's. Cheap to flip later — the bank is data. **Least certain decision in this spec.** |
| 16 | **Leak check** after generation: portrait text scanned for framework vocabulary (névrotisme, Big Five, RIASEC, Schwartz, score, conscienciosité…). Hit → one regeneration with a corrective turn → still hit → draft kept, flagged, counselor UI shows a warning banner. | Layered: prompt rule + code check + human validation. |
| 17 ⚑ | Scoring **errata** fixed in code (see *Scoring* for detail): single-item axis A1 excluded from tension flagging; RIASEC normalised by *computed* maxima (the manual's E=10 / C=10 are 11 / 9); Big Five levels use net ≥ +2 / ≤ −2. | The manual doesn't specify these; each is the smallest rule that makes the sheet behave. All three listed for the PM to confirm. |
| 18 | `PromptVersion.path` widened `String(1)` → `String(16)`; valid values become **prompt slots** = parcours ids ∪ `{voyage_micro, voyage_portrait}`. | Using "4"/"5" would make the two prompts show up as parcours everywhere the registry is iterated. |
| 19 | Small admin addition: `PUT /api/admin/users/<id>/role`. | No endpoint today gives a user the `counselor` role; without one nobody can validate a portrait. |
| 20 | Out of v1: Roue du Sens, simulateur d'aménagement, Conseiller chat, groupes, Jules Verne / Académie skins, counselor dashboard listing voyages by code, under-15 consent, selling the voyage. | See *Out of scope*. |

---

## Data model

```
voyages
  id                      String(36) pk
  user_id                 fk users, index               (many per user; at most one with status in open set)
  status                  String(16): en_cours | s0_termine | termine      ("open" = en_cours | s0_termine)
  sessions_completed      JSON  list of "0".."5"
  consent_at              DateTime
  consent_version         String(16)                    ("voyage-v1")
  age_attested            Boolean
  counselor_code_id       fk counselor_codes, nullable  (set by /unlock; gates S1–S5)
  responses_encrypted     Text  Fernet JSON {item_id: "A" | true | false, "billets": {session: {field: text}}}
  micro_status            String(16): none | generating | success | error
  micro_encrypted         Text  Fernet JSON {phrase, prompt_version_id, tokens_in, tokens_out}
  portrait_status         String(16): none | generating | draft | validated | error
  portrait_encrypted      Text  Fernet JSON {sections: {key: prose}, snapshot: <synthesis>, flags: [], edited: bool,
                                             prompt_version_id, tokens_in, tokens_out}
  portrait_validated_at   DateTime nullable
  validated_by_id         fk users nullable
  share_token             String(64) unique index nullable   (set when S5 completes)
  scoring_version         String(16)                    ("cahier-2026-09")
  tokens_in, tokens_out   Integer nullable              (sum of both calls, for the cost dashboard)
  created_at, updated_at, completed_at

voyage_notes
  id, voyage_id fk cascade, counselor_id fk users, body Text, updated_at
  unique (voyage_id, counselor_id)

analyses.voyage_id        fk voyages nullable            (traceability, like prompt_version_id)
prompt_versions.path      String(1) → String(16)
```

Statuses are strings, not native enums — widening a MySQL ENUM is the one migration step this repo can't rehearse locally (SESSION-LOG).

`Voyage.to_dict()` returns: id, status, sessions_completed, consent_at, age_attested, has_code, micro_status, `micro_phrase` (the one thing the candidate may see), portrait_status, share_token (only when `termine`), created_at, completed_at. **Never** responses, scores, or portrait text — those have their own endpoints with their own access rules.

---

## The question bank — `backend/app/services/voyage/bank.py`

One Python structure, the single source of truth for text *and* weights:

```python
SCORING_VERSION = "cahier-2026-09"

SESSIONS = [
  {"n": "0", "title": "Dans 10 ans", "subtitle": "Ta vision instinctive — 20 affirmations",
   "intro": [...paragraphs verbatim...], "duration": "5 min", "kind": "checklist",
   "items": [{"id": "S0-01", "text": "Travailler dehors, sur le terrain, en mouvement",
              "axes": [("A9", +1)]}, ...,
             {"id": "S0-11", "text": "Avoir un emploi stable avec un salaire régulier", "axes": [("A5", -1)]}, ...],
   "billet": [{"key": "top3", "label": "Les 3 affirmations qui m'ont le plus parlé :"},
              {"key": "surprise", "label": "Quelque chose qui m'a surpris(e) dans mes réponses :"}]},
  {"n": "1", "title": "Ce que tu faisais naturellement", ..., "kind": "scenes",
   "items": [{"id": "S1-1", "title": "La cabane", "subtitle": "Ce que tu construisais avec les autres",
              "narrative": [...], "question": "À cet âge-là… tu te reconnaissais dans quel groupe ?",
              "options": [{"letter": "A", "label": "Les architectes", "text": "Ceux qui dessinaient le plan, qui avaient la vision.",
                           "riasec": {"R": 1, "I": 1, "E": 1, "C": 1}}, ...]}, ...]},
  ...
]
AXES = {"A1": {"label": "Mobilité territoriale", "neg": "Ancrage local", "pos": "Mobilité / international"}, ... "A10"}
```

Per-option tag vocabulary, straight from the counselor manual's *Dimension* column:
`riasec` (points), `axes` (S0 only), `sdt` (autonomie | appartenance | competence), `schwartz` (…), `big5` (signed: `{"ouverture": +1, "nevrotisme": -1}`), `style` (holistique | sequentiel | adaptatif | consultatif), `env` (S4 short labels), `risk`, `sens`. Every option also carries a `plain` string — the short plain-French descriptor the prompt is allowed to use (e.g. `"tu improvises, l'imprévu te réveille"`), never the tag.

`bank.public()` returns the same structure **stripped of every tag key** — that is what `GET /api/voyage/bank` serves. A test walks the served JSON and asserts no scoring key survives.

Item count: 20 (S0) + 6 + 7 + 7 + 6 + 7 = **53 scored items**, plus 20 optional free-text billet fields.

---

## Scoring — `backend/app/services/voyage/scoring.py`

Pure functions over `(responses: dict) -> dict`. No DB, no I/O.

**S0 — bipolar axes.** For each item loading on an axis with sign *s*: OUI contributes `+s`, NON contributes `−s` (manual: « ✓ OUI = +1, ✗ NON = −1 »; items marked `(−)` load on the negative pole — e.g. *Emploi stable* pushes A5 toward *Stabilité*). `resultant` = sum. **Tension** = resultant in [−2, +2] **and the axis has ≥ 2 items** ⚑ — A1 *Mobilité* has a single item (S0-08) so, as written, it would be a tension for every human being and be weighted ×1.5 in every portrait. Excluded until the PM adds items. Output per axis: `{oui, non, resultant, n_items, tension}`; `tensions`: ordered list; `top3`: axes by |resultant| desc (zero excluded), ties broken by axis id, each carrying the **pole label the sign points to** (resultant > 0 → `pos`, < 0 → `neg`) — that label is the only form the phrase prompt and the analyses block ever see.

**S1 — RIASEC.** Sum points per letter over the six scenes. `max` per letter is **computed from the bank** — summing the best option per scene gives R 12 · I 11 · A 10 · S 10 · **E 11 · C 9**; the manual prints E 10 / C 10 ⚑. `normalized = score / max`; `top3` by normalized desc, ties by letter order R I A S E C. A test asserts the computed maxima against these numbers so a transcription slip in the bank is caught.

**S2 — SDT + Schwartz.** Count tag occurrences over S2-1..S2-7 only (the manual's synthesis box sits under Session 2). `sdt_dominant` / `schwartz_dominant` = all tied maxima, reported as a list — no invented tie-break. `ambivalences`: the S2-7 choice, to be explored in restitution.

**S3 — Big Five + style.** Signed counts over S3-1..S3-7 (« Faible Névrotisme » = −1 on nevrotisme, « Introversion » = −1 on extraversion). Level ⚑: net ≥ +2 → *Élevé*, net ≤ −2 → *Faible*, else *Moyen*. `style_dominant` = tied maxima. `intro_extra` = the net extraversion sign in words.

**S4 — environment.** No arithmetic: the chosen option's `env` label per scene → `espace`, `rythme`, `equipe`, `manager`, `irritant`, `vendredi`.

**S5 — risk + meaning.** `risque` = S5-1 label (Fort / Modéré / Calculé / Faible) with S5-2 and S5-3 labels alongside — the manual names all three as sources but gives no combination rule, so none is invented. `valeur_centrale` = S5-4, `trace` = S5-5, `sacrifice` = S5-6, `vivant` = S5-7.

`synthesize(responses) -> dict` assembles the page-18 sheet: `{scoring_version, s0, riasec, s2, s3, s4, s5, completeness}`; sections for incomplete sessions are `None`. `prompt_context(synthesis, micro_phrase, stage) -> list[str]` produces the reduced lines for analyses (see *Injection*).

---

## API — `backend/app/routes/voyage.py`, prefix `/api/voyage`

Candidate (all `@jwt_required`, owner-scoped to the user's open voyage):

| Method | Path | Behaviour |
|---|---|---|
| GET | `/bank` | Text-only bank. |
| GET | `` | Current (open or latest) voyage `to_dict()`, or `{"voyage": null}`. |
| POST | `` | Create. Body `{consent: true, age_attested: true}` — both mandatory, else 400. 409 if an open voyage exists. |
| GET | `/responses` | Decrypted answers + billets, owner only. For resume/re-render. |
| PUT | `/responses` | Merge `{answers: {id: value}, billets: {...}}`. Ids and values validated against the bank; unknown ids dropped, bad values 400. Items of a locked session are rejected 403. |
| POST | `/sessions/<n>/complete` | Requires every item of session *n* answered (400 listing missing ids) and S(n−1) complete (409). `n=0` → `status=s0_termine`, spawns micro generation. `n=5` → `status=termine`, `completed_at`, `share_token`, spawns portrait generation. |
| POST | `/unlock` | `{code}` — same normalisation as `unlock_with_code`; active code → `counselor_code_id`, `uses_count += 1`. |
| GET | `/portrait` | Sections + validated_at, **only when `portrait_status == validated`**; else 409 `{status}`. |
| DELETE | `` | Erase the voyage (cascade notes). |

Counselor (`@role_required("counselor", "admin")` **and** the token — the synthesis sheet is never public-by-token, unlike `/c/<token>` for analyses):

| Method | Path | Behaviour |
|---|---|---|
| GET | `/c/<token>` | `{prenom, tranche_age, situation, synthesis, portrait: {status, sections, flags, edited}}`. The 5-phase restitution guide is static frontend content. |
| PUT | `/c/<token>/portrait` | Replace sections (all six keys, non-empty). Sets `edited=true`. Allowed while draft or validated. |
| POST | `/c/<token>/portrait/regenerate` | Re-run the portrait call (draft only). |
| POST | `/c/<token>/validate` | `portrait_status=validated`, `validated_by_id`, `validated_at`. |
| GET / PUT | `/c/<token>/notes` | This counselor's private note. |

Admin: `PUT /api/admin/users/<id>/role` `{role}` ∈ `candidate | counselor | admin`; `GET /api/admin/stats` gains `voyages: {started, s0_done, completed, validated}`.

Session locking rule (server-side, also mirrored in the UI): S0 open once the voyage exists; S1–S5 need `counselor_code_id` set **and** a Profile with `prenom` and `tranche_age`; S(n) needs `"n-1"` in `sessions_completed`.

---

## Generation — `backend/app/services/voyage/generation.py`

Reuses the analysis runner's shape: daemon thread, `db.session.remove()` before the stream, fresh session to write the result, status → `error` with the message on failure. Two entry points:

**`start_micro(voyage_id, app)`** — slot `voyage_micro`, `tiers.model_for(FREE)`, `max_tokens=200`. User message: the S0 sheet in plain words (top-3 axes as *plain* labels, tensions as « autant coché des deux côtés sur … »), prénom if known. Output: one sentence, 15–25 words (manual: « Micro-révélation à formuler »). Stored encrypted; `micro_status=success`.

**`start_portrait(voyage_id, app)`** — slot `voyage_portrait`, `tiers.model_for(PAID)`, `max_tokens=3000`, structured output with a six-key schema:

```
accroche · qui_tu_es · vibrer · besoins · chemins · pas_encore   (each: string)
```

User message = `--- PROFIL DE BASE ---` (prénom, tranche d'âge, situation, projet if any) + `--- CE QUE TU AS CHOISI ---` (per scene: the chosen option's `plain` descriptor — the person's own words, never the tag) + `--- SYNTHÈSE ---` (RIASEC universes as words, tensions as plain axis labels ×1.5 note, SDT need, style, S4 words, S5 words). **No numbers, no trait names, no framework names** — the same reduction discipline as bloc 5's `prompt_context()`.

After the call: `leak_check(sections)` (word-boundary, case-insensitive: névrotisme, neuroticisme, big five, riasec, schwartz, sdt, dunn, kahneman, dweck, frankl, logothérapie, conscienciosité, agréabilité, extraversion, introversion, \bscore\b, \btrait\b). Hit → one retry with an appended user turn quoting the offending words → still hit → keep, `flags=["vocabulaire"]`. Stored encrypted with the synthesis snapshot; `portrait_status=draft`.

Seed scripts `seed_prompt_v10_voyage_micro.py` and `seed_prompt_v10_voyage_portrait.py`, **seeded active** (without them the feature errors on first use — same rationale as `seed_prompt_v11_p3.py`). The portrait prompt is drafted from the manual's page-20 template and page-2 wording table: prose only in sections 1–4, never a named métier (« les gens qui… », « les endroits où… »), never « Tu es… », tone « un ami très intelligent qui te connaît bien », accroche = one metaphor. The PM edits from there.

---

## Injection into analyses

`routes/analyses._merge_profile()` gains, after the profile fold:

```python
voyage = Voyage.for_prompt(user_id)   # latest validated portrait, else latest with a phrase
if voyage:
    inputs["_voyage_id"] = voyage.id
    stage = "validated" if voyage.portrait_status == "validated" else "s0"
    inputs["_voyage"] = prompt_context(voyage.synthesis(), voyage.micro_phrase, stage)
```

`Analysis.voyage_id` is set from `_voyage_id` at creation. `anthropic_service._voyage_block(inputs)` appends to **every** parcours message:

```
--- CE QUE LE VOYAGE A RÉVÉLÉ ---
Phrase révélée : <micro>
Ce qui l'attire le plus dans dix ans : le terrain et l'action, transmettre, un impact visible
                                  ── validated stage adds ──
Univers dominants : Réaliste, Entreprenant, Investigateur
Besoin dominant : autonomie
Ambivalences relevées : sécurité vs risque · solo vs collectif
Cadre où elle donne le meilleur : bureau fermé et calme · cycles courts · petite équipe soudée
Ce qui l'épuise : les interruptions constantes
Ce qui la met en colère : l'injustice
Se sent vivant(e) quand : elle crée
```

Stored on the analysis as `inputs["_voyage"]` — reduced, plain, no numbers — the same tier of data as `_conditions`. The rapport and `/c/<token>` pages don't render it. Absent voyage → no block, no key.

---

## Frontend

```
frontend/src/app/voyage/page.tsx                 hub: intro, consent + age, 6-session progress, per-state CTA,
                                                  micro-phrase after S0, code entry, portrait link when validated
frontend/src/app/voyage/session/[n]/page.tsx     the player: one scene per screen; S0 is one scrolling list of 20
                                                  ✓/✗ rows; last screen = billet de sortie (optional) + « Terminer »
frontend/src/app/voyage/portrait/page.tsx        candidate portrait (validated only), print CSS via .report-shell
frontend/src/app/voyage/c/[token]/page.tsx       counselor: synthesis sheet (axes + tensions, RIASEC bars, S2–S5
                                                  boxes), draft editor (6 textareas), leak-flag banner, regenerate,
                                                  private notes, « Valider et transmettre », restitution guide
frontend/src/components/voyage/*                 SessionProgress (6 stamps), SceneCard, OptionCard, ChecklistRow,
                                                  BilletForm, MicroReveal, SynthesisSheet, RiasecBars
frontend/src/types/voyage.ts                     bank + voyage + portrait types (bank shapes come from the API —
                                                  no French copy duplicated in TS)
```

Entry points: **`/analyse` chooser** gets the voyage as a full-width primary card above the three parcours (« 5 minutes pour commencer. Ce qu'il révèle enrichit toutes vos analyses. »); **landing** gets a section for it above the three scenario cards; **`/espace`** gets a voyage status card at the top (progress, phrase teaser, next action); **AppBar** dropdown gets « Mon voyage ». `proxy.ts` adds `/voyage` to `PROTECTED`.

Player behaviour: answers are `PUT` on every « Suivant » (merge semantics, so a lost connection loses one scene, not a session). Resume from the first unanswered item. Locked sessions render the reason (« Avec un conseiller », « Complétez votre profil ») and the code field, never a dead button. After S0 completion the hub polls `GET /api/voyage` every 2 s while `micro_status == generating` (Haiku: a few seconds).

Copy: sessions and portrait reproduce the cahier verbatim (⚑ decision 15). Chrome is vouvoiement and respects the CLAUDE.md ban list. Colour: the voyage gets its own accent bar so it reads as a fourth scenario, not a fourth parcours (charter teal is taken by parcours 3 — implementation picks from the charter, with the `frontend-design` skill).

---

## Admin

- `/admin/prompts`: selector gains two slots — « Voyage · phrase (S0) » and « Voyage · portrait ». `_read_path()` validates against `prompt_slots.valid()`; `test_seed_scripts.py`'s literal regex widens from `(\w)` to `(\w+)`.
- `/admin/utilisateurs`: role select per row → `PUT /admin/users/<id>/role`.
- `/admin`: a voyage KPI row (started / S0 done / completed / validated).
- Costs: voyage tokens are recorded on the row; folding them into `/admin/couts` is a follow-up.

---

## Security & RGPD checklist

- Answers, portrait and phrase: Fernet ciphertext columns; `to_dict()` never carries them; raw-column test like `test_columns_hold_ciphertext_not_plaintext`.
- Scores exist only in memory and, encrypted, inside the portrait snapshot. No endpoint returns them to a candidate.
- Counselor endpoints: role **and** token. The synthesis sheet is never reachable by link alone.
- No logging of answers, scores or portrait text anywhere; error paths log the exception only.
- Consent + age attestation stored with a version; the voyage cannot be created without both.
- `DELETE /api/voyage` erases independently of the profile.
- The `_voyage` block on analyses contains no numbers and no framework words — a test asserts it.

---

## Testing

Backend (pytest, SQLite in-memory as today):

- `test_voyage_bank.py` — 53 items, unique ids, every option tagged, computed RIASEC maxima = R12 I11 A10 S10 E11 C9, every S0 item loads on ≥1 axis, `bank.public()` carries no weight keys.
- `test_voyage_scoring.py` — S0 with reversed items and the tension band; A1 never a tension; RIASEC worked example from the manual; ties reported as lists; Big Five thresholds; S5 mapping; incomplete session → `None` section.
- `test_voyage_routes.py` — create needs consent + age; owner-only responses; validation of ids/values; complete needs all items and order; S1 locked without code / without profile; unlock increments `uses_count`; S5 sets `share_token` and spawns generation (mocked); portrait 409 until validated; counselor endpoints 403 for candidates; validate flips status; DELETE erases; ciphertext at rest.
- `test_voyage_prompt_context.py` — no digits, no banned words; S0 stage vs validated stage; absent voyage → no block; every parcours' `_format_user_message` includes the block when present.
- `test_voyage_generation.py` — schema has exactly six keys; leak check → retry → flag; missing slot prompt → `error`.
- `test_prompt_slots.py`, `test_seed_scripts.py` updated.

Frontend: no runner in the repo — `npm run lint` + `npm run build`, and a new **§ 10 Voyage** in `TEST-PLAN.md` (manual, PM-facing, same row format).

---

## Phases — each ships on its own (git push = deploy)

| Phase | Deliverable | Visible? |
|---|---|---|
| 0 | Bank + scoring + tests (TDD, pure Python) | No |
| 1 | Models, 4 migrations, encryption, consent, routes, unlock, admin role endpoint | API only |
| 2 | Prompt slots, seeds, micro + portrait generation, leak check, `/admin/prompts` selector | Admin |
| 3 | Candidate UI: hub, player, billets, micro reveal, portrait page, chooser/landing/espace/AppBar entries | Yes |
| 4 | Counselor UI: synthesis sheet, editor, validate, notes, restitution guide | Yes |
| 5 | Injection into analyses, `Analysis.voyage_id`, TEST-PLAN §10, CLAUDE.md (voyage section; « Portrait module » leaves *Out of scope*) | Yes |

Rough size: ~6–7 developer-days; ~14 new backend files, ~12 new frontend files, 4 migrations.

---

## For the PM — not blocking, decided by default

1. **Tone** (⚑15): tutoiement inside the voyage, vouvoiement around it. Say the word and the bank flips.
2. **Under-15** (⚑13): v1 attests 15+. The cahier's *Classe* field says younger users exist; a parental-consent flow is a separate piece.
3. **Scoring errata** (⚑17): A1 has one item; RIASEC E/C maxima are 11/9 not 10/10; no Big Five thresholds in the manual. Defaults chosen; confirm or correct.
4. **Roue du Sens** (Parcours §7): six wheel dimensions with no definition in either PDF. Not built.
5. **Simulateur d'aménagement**: referenced 3× in the counselor manual (S4 answers « pré-remplissent » its Q1, Q5/Q6, Q9), specified nowhere. Not built; bloc 5 already covers adjacent ground.
6. **Jules Verne / Académie des Ori skins** (⚑2): presentation layer, later.
7. **Counselor dashboard** listing voyages redeemed with a given code: follow-up; v1 uses the share link the candidate passes on, as analyses do.
8. **If a counselor never validates**, the candidate keeps S0's phrase and sees « en attente de validation ». No escape hatch, by the ruling.

## Out of scope (v1)

Roue du Sens · simulateur d'aménagement · Conseiller Neoori chat · groupes d'échange · Jules Verne / Académie skins · counselor dashboard · under-15 consent · selling the voyage · editing the bank from the admin UI.
