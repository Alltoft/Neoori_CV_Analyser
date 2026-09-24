# Comptes conseiller — Design Spec
Date: 2026-09-24
Status: proposed — developer decisions marked ⚑ are defaults, override any of them

## Overview

Today a conseiller is nothing but `users.role == 'counselor'`, granted by hand
from `/admin/utilisateurs`, and a "counselor code" is an unrelated object the
admin mints in `/admin/conseillers`. The two mechanisms never meet: no column
ties a conseiller to the codes their bénéficiaires redeem, and
`CounselorCode.uses_count` is a bare integer — no who, no when.

This spec turns the conseiller into a first-class account:

1. A conseiller **applies for an account** themselves. The admin **approves or
   rejects** the demande. The admin no longer creates conseillers by hand.
2. An approved conseiller **mints their own codes**, within two limits the
   admin sets: how many codes, and how many uses per code.
3. A conseiller gets a **dashboard** — their codes, their bénéficiaires, and
   how many accompagnements they have carried out.

Developer rulings in this conversation (2026-09-24):

- Quota model: unlimited by default, **admin can cap**. After the multi-use
  objection, the cap became two dials, not one total (decision 4).
- Approval file: structure + email pro + téléphone, **no document upload**.
- Dashboard shows bénéficiaires **identified, no content** (decision 9).
- « Conseillé » counts **validated portraits** (decision 10).
- Email is **built now**, two FR templates.
- A pending conseiller **can log in** and sees a waiting screen.
- The admin **keeps** direct code minting for structures with no account.
- Codes are **single-use by default, with an expiry**.

This supersedes decision 20 of `2026-09-09-voyage-design.md`, which parked
"counselor dashboard listing voyages by code" out of v1, and decision 19 of the
same spec, which made `PUT /api/admin/users/<id>/role` the only way to create a
conseiller. That endpoint stays — approval now drives it internally.

---

## Decisions

| # | Decision | Why |
|---|---|---|
| 1 | The demande lives in a **new table `counselor_profiles`**, 1-1 with `users`. `users` gains no column. | `users` is lean (9 columns) and `to_dict()` is returned to every candidate on every `/auth/me`. Counselor fields there would leak into every payload and every test fixture. |
| 2 | A pending conseiller is a **real `User` with `role='candidate'`** until approval. | `role_required` reads the JWT claim (`utils/decorators.py:13`). A pending account holding `role='counselor'` would pass every `/api/voyage/c/<token>` guard before anyone reviewed it. Keeping the role until approval makes early access impossible by construction, not by a check someone can forget. |
| 3 | On approval, `user.role` flips to `counselor`; the frontend calls `POST /api/auth/refresh`, which re-reads `user.role` from the DB (`auth.py:93-99`). | Access TTL is 1 h (`config.py:23`). Without the refresh the conseiller waits up to an hour for an approval they can see on screen. No new mechanism — the endpoint already does this. |
| 4 | Two admin dials, **not** an account-wide redemption quota: `max_codes` (how many codes this conseiller may create) and `max_uses_per_code` (ceiling on any one code). Both `NULL` = illimité. | A total quota is meaningless once a code is multi-use — developer's objection, 2026-09-24. The effective budget is `max_codes × max_uses_per_code`, and both halves are things the admin actually wants to say. |
| 5 | `max_codes` counts **codes ever created**, not active ones. | Counting active codes lets a conseiller revoke an unused code and mint a fresh one forever. Cost: a mis-labelled code burns a slot and the conseiller must ask for a raise. The loophole is worse than the annoyance. |
| 6 ⚑ | Codes are **single-use by default** (`max_uses = 1`), with `expires_at` **default 90 days**. A collective code is the same object with a higher `max_uses`, clamped to `max_uses_per_code`. | A permanent code is one screenshot away from a Facebook group of demandeurs d'emploi, and then it is unlimited free Premium until someone notices. Single-use also means the code carries a name: « Karim — utilisé le 12/09 » instead of « CODE-4F2K — 14 utilisations ». There is no separate "permanent code" concept to build: set the number high. |
| 7 | Every redemption is logged in a **new table `code_redemptions`** (code, user, target, timestamp). `uses_count` stays updated for the existing admin page. | `uses_count` cannot answer "by who, when", and an analysis unlock records *that* a code was used (`Analysis.unlock_method`) but never *which*. The dashboard the developer asked for is not derivable from what is stored today. |
| 8 | Limits are enforced **at redemption and at minting**, both against `COUNT(code_redemptions)` — one source of truth. | `uses_count` is an increment that can drift; a count cannot. |
| 9 | The dashboard shows bénéficiaires **identified (prénom, email, date), never their content**. No link to their voyage or analysis. | Developer ruling. Reaching a voyage still requires the candidate to hand over their token, exactly as today. Keeps « mes bénéficiaires » and « leurs données » on opposite sides of a line. |
| 10 | « Accompagnements » = **portraits this conseiller validated** (`Voyage.validated_by_id`). | Already recorded, attributable, and it is real work. Shown beside « Bénéficiaires » (codes used) so handing out a code is never counted as doing the work. |
| 11 | New guard `approved_counselor_required`: JWT claim **and** a DB check that `counselor_profiles.status == 'approved'`. | Revocation must bite immediately. A claim-only guard leaves a revoked conseiller working for up to an hour. |
| 12 | Rejection is **terminal** — no re-apply flow in v1. `rejected` (never approved) and `revoked` (was approved, removed afterwards) are **separate statuses**. | Developer chose "logged in, waiting screen" over the re-apply variant. A rejected person who should not have been can be fixed by the admin flipping the row. The two end states are kept apart because they are not the same fact: one is a demande that failed review, the other is a conseiller who worked and whose access was withdrawn — different message on screen, different line in any report. |
| 13 | The admin **keeps** `POST /api/admin/counselor-codes`. Existing codes get `owner_id = NULL` and stay admin-owned. | Structures without an account still need codes, and no backfill means no migration risk on live rows. |
| 14 | Email via a new `app/services/email_service.py` (Resend), **fail-soft**. | `resend==2.30.0` is installed and `RESEND_API_KEY` is configured, but zero lines of email code exist — this is the app's first transactional mail. A Resend outage must not 500 an approval that already committed. |
| 15 | Bundled fix: **`/admin` frontend role guard**. | `frontend/src/app/admin/layout.tsx` has no role check. A signed-in candidate typing `/admin` passes the proxy (cookie presence only, `proxy.ts:13`) and renders the entire admin shell; only the data 403s. Adding an admin section to a shell anyone can open is not acceptable. |
| 16 ⚑ | Out of v1: conseiller↔bénéficiaire messaging, conseiller-initiated invitations by email, structure-level accounts (several conseillers under one Cap Emploi), code re-issue, CSV export of the dashboard. | See *Out of scope*. |

---

## Data model

### New: `counselor_profiles`

One row per demande, one demande per account.

| Column | Type | Notes |
|---|---|---|
| `id` | String(36) | uuid4 |
| `user_id` | String(36) FK `users.id` | **unique**, indexed |
| `structure` | String(255) | required — Cap Emploi, France Travail, Mission locale, autre |
| `fonction` | String(255) | required |
| `telephone` | String(32) | required |
| `email_pro` | String(255) | nullable — may differ from the login email |
| `message` | Text | nullable — free-text motivation |
| `status` | Enum `pending/approved/rejected/revoked` | default `pending`, indexed |
| `max_codes` | Integer | **nullable** = illimité |
| `max_uses_per_code` | Integer | **nullable** = illimité |
| `decision_reason` | Text | nullable — the rejection reason, or the revocation reason |
| `reviewed_at` | DateTime | nullable |
| `reviewed_by_id` | String(36) FK `users.id` | nullable |
| `created_at` | DateTime | |

### Changed: `counselor_codes`

| Column | Type | Notes |
|---|---|---|
| `owner_id` | String(36) FK `users.id` | **nullable**, indexed. `NULL` = admin-minted. Every existing row becomes `NULL` with no backfill. |
| `max_uses` | Integer | **nullable** = illimité. New codes default to `1`. |
| `expires_at` | DateTime | nullable. New codes default to now + 90 days. |
| `revoked_at` | DateTime | nullable. Complements the existing `is_active`. |

`code`, `label`, `created_by_id`, `is_active`, `uses_count`, `created_at` are
unchanged. `created_by_id` keeps meaning "who pressed the button"; `owner_id`
means "whose budget and dashboard this belongs to". For a conseiller-minted
code they are the same user.

### New: `code_redemptions`

| Column | Type | Notes |
|---|---|---|
| `id` | String(36) | uuid4 |
| `code_id` | String(36) FK `counselor_codes.id` | indexed |
| `user_id` | String(36) FK `users.id` | **nullable**, indexed — see below |
| `target_type` | Enum `analysis/voyage` | |
| `target_id` | String(36) | |
| `redeemed_at` | DateTime | indexed — the dashboard's time axis |

Unique constraint on `(code_id, target_type, target_id)` so a retried request
cannot double-count.

`user_id` is nullable because `POST /api/analyses/<id>/unlock` carries **no auth
decorator** (`analyses.py:190`) — the anonymous analysis flow is supported and
must keep working. An anonymous redemption counts toward the code's uses and
appears in the dashboard as « Bénéficiaire anonyme ».

### Status machine

```
                          ┌──reject──▶ rejected   (never approved, terminal)
(no row) ──apply──▶ pending
                          └─approve──▶ approved ──revoke──▶ revoked
                                                            (was approved, terminal)
```

`user.role` is a function of this column: `approved` ⇒ `counselor`, anything
else ⇒ `candidate`. The transition writes both in one commit.

---

## Flows

### 1. Demande

New page `/inscription-conseiller`, reusing `AuthLayout`. Fields: email, mot de
passe (min 8), prénom, structure, fonction, téléphone, email pro, message,
consent CGV. `POST /api/counselor/apply` creates the `User` (role `candidate`)
and the profile (`pending`), sets both cookies, and the client lands on
`/conseiller`.

An **already-registered candidate** can apply from their espace. The same
endpoint, called with a valid JWT, skips account creation and only writes the
profile. This prevents a conseiller from ending up with two accounts.

Rejected by the endpoint: a second demande from an account that already has a
profile row (409, « Une demande existe déjà pour ce compte. »).

`POST /api/counselor/apply` is the app's only public endpoint that creates an
account *and* enqueues admin work, so it is the one worth abusing. v1 relies on
the unique-email constraint and on the queue being reviewed by a human; if
demandes are ever spammed, the answer is a rate limit on this route, not a
captcha (open question 6).

### 2. Review

`/admin/conseillers` gains a **Demandes** panel above the existing codes panel,
defaulting to `status=pending`, with the count in the tab label.

Each row expands to the full file (structure, fonction, téléphone, email pro,
message, date). Two actions:

- **Approuver** — opens `max_codes` and `max_uses_per_code` inputs, both blank
  = illimité. Writes `status=approved`, `reviewed_at/by`, flips `user.role`,
  sends the approval mail.
- **Refuser** — requires a reason. Writes `status=rejected` and the reason,
  sends the rejection mail.

On an already-approved account: **Modifier les limites** and **Révoquer**
(status → `revoked`, role → `candidate`, their codes stay valid unless the
admin also deactivates them — revoking the person is not the same as burning
codes bénéficiaires already hold).

### 3. Conseiller dashboard

Route `/conseiller`, one page, four states driven by `GET /api/counselor/me`:

- `pending` — « Votre demande est en cours d'examen. » plus what they submitted.
- `rejected` — the reason, and no further action.
- `revoked` — « Votre accès conseiller a été retiré. » plus the reason. Their
  past codes and bénéficiaires are not shown; the account keeps working as a
  candidate account.
- `approved` — the dashboard:
  - **Tiles**: Bénéficiaires (distinct redemptions) · Accompagnements (portraits
    validated) · Codes restants (`max_codes` − created, or « illimité ») ·
    Codes en circulation (active, unused, unexpired)
  - **Mes codes**: label, code, statut (actif / utilisé / expiré / révoqué),
    créé le, utilisé le, par qui
  - **Générer un code**: label (prénom ou référence dossier), places (default 1,
    clamped), expiration (default 90 j)
  - **Mes bénéficiaires**: prénom, email, date d'utilisation. No content link.

### 4. Redemption

Both existing call sites gain the same three steps before unlocking:

| Check | Response |
|---|---|
| inactive or revoked | 400 « Code invalide ou désactivé. » (existing string) |
| `expires_at` passed | 400 « Ce code a expiré. » |
| redemptions ≥ `max_uses` | 400 « Ce code a atteint sa limite d'utilisation. » |

On success: unlock as today, `uses_count += 1`, **and** insert the
`code_redemptions` row in the same transaction.

Sites: `analyses.py:190-215` (`target_type='analysis'`, `user_id` may be NULL)
and `voyage.py:441-484` (`target_type='voyage'`, always authenticated).

---

## API surface

New blueprint at `/api/counselor`. The existing `/api/c` share-link blueprint
(`routes/counselor.py`) is untouched — different object, different audience.

| Method + path | Guard | Purpose |
|---|---|---|
| `POST /api/counselor/apply` | public or authed | submit the demande |
| `GET /api/counselor/me` | `@jwt_required()` | profile, status, limits — the three-state switch |
| `GET /api/counselor/stats` | `approved_counselor_required` | the four tiles |
| `GET /api/counselor/codes` | idem | own codes + redemption info |
| `POST /api/counselor/codes` | idem | mint, clamped |
| `DELETE /api/counselor/codes/<id>` | idem | revoke — own, unredeemed only |
| `GET /api/counselor/beneficiaires` | idem | prénom, email, date |

Admin, on the existing `/api/admin` blueprint:

| Method + path | Purpose |
|---|---|
| `GET /api/admin/counselor-applications?status=` | the queue |
| `POST /api/admin/counselor-applications/<id>/approve` | `{max_codes?, max_uses_per_code?}` |
| `POST /api/admin/counselor-applications/<id>/reject` | `{reason}` |
| `PUT /api/admin/counselor-applications/<id>/limits` | adjust after approval |
| `POST /api/admin/counselor-applications/<id>/revoke` | `{reason}` — approved → revoked, role back |

`GET/POST/DELETE /api/admin/counselor-codes` keep working unchanged
(decision 13).

### Authorization

New decorator in `app/utils/decorators.py`:

```python
def approved_counselor_required(fn):
    """Claim says counselor AND the DB says the account is still approved.

    role_required alone reads the JWT claim, which survives a revocation for
    up to the access-token TTL (1 h).
    """
```

Admin passes it too — an admin opening a conseiller surface for support is the
same exception `role_required("counselor", "admin")` already makes everywhere
in `voyage.py`.

---

## Email

New `app/services/email_service.py`:

```python
def send(to: str, subject: str, html: str) -> bool   # returns False on failure, never raises
def send_counselor_approved(user, profile) -> bool
def send_counselor_rejected(user, profile) -> bool
```

FR templates, sober, CLAUDE.md ban list applies. Both mails state what happens
next; the approval mail links to `/conseiller`. A `False` return is logged with
the user id and does not roll back the decision — the conseiller still sees the
result on their next visit.

Requires a verified sender domain on `neoori.tech`. `RESEND_API_KEY` is already
in `config.py:28` and `.env.example:10`; the VPS `.env` needs the real value and
a `MAIL_FROM` alongside it.

---

## Frontend surfaces

| Path | Change |
|---|---|
| `frontend/src/app/(auth)/inscription-conseiller/page.tsx` | new — demande form |
| `frontend/src/app/conseiller/page.tsx` | new — three-state dashboard |
| `frontend/src/app/admin/conseillers/page.tsx` | add the Demandes panel |
| `frontend/src/app/admin/layout.tsx` | **add the missing role guard** (decision 15) |
| `frontend/src/components/layout/AppBar.tsx` | « Espace conseiller » when `role === 'counselor'` |
| `frontend/src/proxy.ts` | add `/conseiller` to `PROTECTED` |
| `frontend/src/lib/counselor.ts` | new — typed client for `/api/counselor/*` |
| `frontend/src/types/index.ts` | `CounselorProfile`, `CounselorCode`, `Redemption` |

Reuse, do not reinvent: `StatCard`, `Table*`, `Badge`/`StatusBadge`, `Card*`,
`Alert*`, `Dialog*`, and `lib/format.ts` (`fmtInt`, `fmtDate`, `fmtDateTime`,
`roleLabel`). The dashboard follows `admin/page.tsx`'s header + tile grid
idiom; the codes panel follows `admin/conseillers/page.tsx`'s two-panel layout.

The role-check pattern to copy is `voyage/c/[token]/page.tsx:91-92` plus its
redirect at `:135-137` and its refusal card at `:386-409` — check before any
fetch, not after.

---

## RGPD

- `/confidentialite` gains a line: a conseiller whose code you use sees your
  prénom, your email and the date of use — and nothing of your analyse or of
  your voyage.
- The demande form's consent checkbox covers the conseiller's own professional
  data (structure, fonction, téléphone).
- On candidate erasure, `code_redemptions.user_id` is set to `NULL`: the count
  survives for the conseiller's statistics, the person does not. Same shape as
  the existing voyage-erasure rule in CLAUDE.md.
- `counselor_profiles` is deleted with the user account.

---

## Testing

Backend (`backend/tests/test_counselor_accounts.py`, TDD — test first):

1. apply creates a pending profile and a `candidate` role
2. a second apply on the same account is 409
3. a pending conseiller is refused by every `/api/counselor/*` guarded route
4. approve flips the role; `/auth/refresh` mints the new claim
5. reject stores the reason and leaves the role alone
6. revoke blocks the conseiller **before** the token expires (decision 11)
7. minting above `max_codes` is refused
8. `max_uses` above `max_uses_per_code` is clamped, not rejected
9. an exhausted code is refused at both redemption sites
10. an expired code is refused at both redemption sites
11. a redemption row is written at both sites, with the right `target_type`
12. an anonymous analysis unlock writes `user_id = NULL` and still counts
13. the unique constraint makes a replayed unlock a no-op, not a double count
14. a conseiller cannot read another conseiller's codes or bénéficiaires
15. admin-minted codes (`owner_id IS NULL`) still redeem, unclamped

Frontend: the three dashboard states render from `GET /api/counselor/me`, and
`/admin` refuses a candidate before fetching.

---

## Migration

One hand-written revision extending head `d6e7f8a9b0c1`, following the
convention from `a1b2c3d4e5f6` onward: sequential id, prose docstring,
**idempotent** (the container runs `db upgrade` at boot,
`backend/entrypoint.sh:24`), guarded with an inspector check per column and per
table. `backend/tests/test_migration_chain.py` asserts a single head, so the
new revision must be the only child of `d6e7f8a9b0c1`.

No data migration: existing codes take `owner_id = NULL`, `max_uses = NULL`,
`expires_at = NULL` and behave exactly as before.

---

## Out of scope

- Messagerie conseiller ↔ bénéficiaire
- Conseiller-initiated email invitations (the conseiller hands over a code; the
  app does not mail the candidate on their behalf)
- Structure-level accounts — several conseillers sharing one Cap Emploi budget
- Re-apply after rejection (decision 12)
- CSV / PDF export of the dashboard
- Portrait module — unchanged, see CLAUDE.md

---

## Open questions for the PM

1. **Who approves?** This spec assumes the single existing admin. If several
   people review demandes, `reviewed_by_id` already records which one, but
   nothing notifies them — decision 14's mail goes to the conseiller only.
2. **Default limits.** Is there a standard grant (e.g. 25 codes, 1 use each) to
   pre-fill the approval form, or does every demande get a judgement call?
3. **Does a revoked conseiller's outstanding codes die with them?** This spec
   says no — bénéficiaires holding a code keep it. Confirm.
4. **90-day expiry** — a placeholder chosen for this spec, not a PM ruling.
5. **Is « conseiller » the right word on the public signup page**, or should it
   name the structures (« Vous accompagnez des demandeurs d'emploi ? »)?
6. **Rate limiting on `/apply`** — worth adding at launch, or wait until the
   queue is actually spammed?
