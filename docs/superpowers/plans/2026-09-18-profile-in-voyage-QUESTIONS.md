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
