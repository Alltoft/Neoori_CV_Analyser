# Mails transactionnels, lot 2 — Design Spec
Date: 2026-10-02
Status: approved 2026-10-02; amended the same day while planning (see « Amendments »)

## Overview

The app sends four mails today: conseiller approved, conseiller rejected,
verify your address, reset your password (`services/email_service.py`). A
walkthrough on 2026-10-01 found four moments where someone is promised a mail,
or plainly needs one, and gets nothing:

1. **Analysis finished.** Generation runs in a background thread
   (`anthropic_service._run_analysis`). The waiting page gives up polling after
   10 minutes and says « L'analyse a expiré », while the server may still
   finish. A candidate who closes the tab is never told the report exists.
2. **New conseiller demande.** The signup page promises « réponse sous 48 h
   ouvrées »; the admin is never told a demande arrived.
3. **Conseiller revoked.** The pending screen promises « Vous recevrez un email
   dès qu'elle aura été traitée »; approve and reject mail, revoke does not.
4. **Password changed.** A reset ends the other sessions but tells nobody, so
   the owner of a hijacked inbox would not learn their password moved.

This spec adds five mails (the analysis outcome is two: ready, failed) and
changes two lines of the waiting page.

## Decisions

Developer rulings, 2026-10-01 (scope) and 2026-10-02 (design):

1. **The four mails above, nothing else.** PM decides first: a mail to the
   candidate when a portrait is validated; telling the conseiller a
   bénéficiaire finished S5 (conflicts with conseiller spec decision 9).
   Never: voyage content or scores in a mail, a welcome mail, login alerts,
   nudges (no consent for marketing). Receipts are Stripe's job (switch on +
   pass `customer_email`), not Resend's.
2. **Ready mail: always.** Every finished generation mails the candidate, even
   one who watched the bar reach 100 %. No "did they leave" tracking — no
   migration, no write per poll, no guess.
3. **Admin mail goes to every verified admin**, looked up at send time
   (`role = 'admin'` and `email_verified_at IS NOT NULL`). No env var: adding
   or removing an admin in `/admin` moves the mail with it.
4. **Failed paid regeneration: « répondez à ce message ».** The dead end stays
   unfixed in code (retry → 409); the mail gives the candidate a way out
   through the reply address, with the analysis id as a reference. Relaunching
   it is manual work for the team.
5. **Waiting page tells the truth about the mail**: one line while running,
   and the 10-minute client give-up becomes « plus long que prévu », not an
   error.
6. **Explicit calls after each commit** — the approve/reject pattern. Rejected:
   SQLAlchemy `after_update` hooks (would fire from the reaper, admin scripts
   and fixtures, and inside uncommitted transactions); an outbox table + worker
   (new table, process and container for five fail-soft mails).
7. **No content in any mail.** No report text, no voyage text, no applicant
   data. The mail says something happened and links to where it can be read
   behind a login.
8. **No mail to an address nobody proved.** Every recipient here has
   `email_verified_at` set; legacy anonymous analyses (`user_id` NULL) get
   nothing.

## Mails

All five: sober French; opened by « Bonjour {prénom}, » when the profile has a
prénom, « Bonjour, » otherwise (as `send_verification` does); HTML and
plain-text parts built from one paragraph list; the existing footer
« neoori — pour nous écrire, répondez à ce message. »; sender `MAIL_FROM`;
links from `APP_URL`.

### Analysis ready — first run

- To: the analysis owner
- Subject: « Votre analyse est prête »
- Title: « Analyse prête »
- Body: « Votre analyse est prête. Elle est enregistrée dans votre espace. »
- Button: « Ouvrir mon espace » → `{APP_URL}/espace`

### Analysis ready — after an unlock

"After an unlock" = the row has `unlock_method` set (`unlock_service` writes
it before the second run, for Stripe and for a counselor code alike). Not the
paid *tier*: a first run can already be on it.

- Subject: « Votre analyse complète est prête »
- Title: « Analyse complète prête »
- Body: « La version complète de votre analyse est prête. Elle remplace la
  version précédente dans votre espace. »
- Button: « Ouvrir mon espace » → `{APP_URL}/espace`

### Analysis failed — first run

Statuses `error` and `timeout`, including the early « Aucun prompt actif »
error.

- Subject: « Votre analyse n'a pas abouti »
- Title: « Analyse interrompue »
- Body: « La génération de votre analyse n'a pas abouti. Vous pouvez relancer
  une analyse depuis votre espace. »
- Button: « Ouvrir mon espace » → `{APP_URL}/espace`

### Analysis failed — after an unlock

- Subject: « Le déblocage de votre analyse n'a pas abouti »
- Title: « Déblocage interrompu »
- Body: « Votre déblocage est bien enregistré, mais la version complète n'a
  pas pu être générée. Répondez à ce message : nous la relançons pour vous. »
  then « Référence : {analysis.id} »
- No button: the espace offers nothing that helps (unlock → 409).

### New conseiller demande → admins

- To: each verified admin, one send per address
- Subject: « Nouvelle demande de compte conseiller »
- Title: « Nouvelle demande »
- Body: « Une demande de compte conseiller attend votre décision. »
- Button: « Voir les demandes » → `{APP_URL}/admin/conseillers`
- Nothing about the applicant — name, structure, phone, SIRET stay in the
  dashboard.

### Conseiller revoked

- To: the conseiller's account address (`profile.user.email`)
- Subject: « Votre accès conseiller »
- Title: « Accès conseiller retiré »
- Body: « Votre accès conseiller a été retiré. » / the revocation reason, in
  the same grey box as the rejection mail, HTML-escaped / « Les codes que vous
  avez déjà remis restent valables. Votre compte reste utilisable comme compte
  candidat. »
- No button.
- The reason is already shown to the conseiller on `/conseiller`
  (`frontend/src/app/conseiller/page.tsx:213`), and the admin UI treats it as
  "the revocation reason shown to the conseiller"; the mail adds no new
  disclosure.

### Password changed

- To: the account address
- Subject: « Votre mot de passe a été modifié »
- Title: « Mot de passe modifié »
- Body: « Le mot de passe de votre compte neoori vient d'être modifié. » /
  « Si c'est vous, il n'y a rien à faire. » / « Si vous n'êtes pas à l'origine
  de ce changement, choisissez-en un nouveau tout de suite. »
- Button: « Choisir un nouveau mot de passe » → `{APP_URL}/mot-de-passe-oublie`

## Backend

### `services/email_service.py`

- `_link_mail(paragraphs, label, link, small)` becomes
  `_mail(paragraphs, *, button=None, small=None) -> (html, text)`.
  `button` is `(label, href)`; `small` is the closing small print; a
  paragraph wrapped in `_Quote(...)` — a reason — renders in the grey box,
  escaped like the rest. The verification and reset mails move to it with
  byte-identical output (pinned by a test against the bytes `_link_mail`
  produced).
- `send_counselor_approved` / `send_counselor_rejected` are not touched.
- New builders, fail-soft like every mail here (catch, log, return False):
  - `send_analysis_ready(to: str, prenom: str, *, unlocked: bool) -> bool`
  - `send_analysis_failed(to: str, prenom: str, *, unlocked: bool, analysis_id: str) -> bool`
  - `send_new_demande(admin) -> bool` — the admin's `User`, for the greeting
  - `send_counselor_revoked(profile: CounselorProfile) -> bool`
  - `send_password_changed(user) -> bool`

  The two analysis builders take plain values, not ORM objects, so the
  generation thread can release its DB connection before the HTTP call to
  Resend (below).

### `services/anthropic_service.py` — `_run_analysis`

Every exit that writes a final status (`success`, `error`, `timeout`,
including the « Aucun prompt actif » early return) ends with
`_notify_outcome(analysis_id)` after its `commit()`:

1. Load the analysis and its user. Return without a mail when `user_id` is
   NULL, the user is gone, or `email_verified_at` is NULL.
2. Read what the mail needs: address, prénom, `status`, `unlock_method`, id.
3. `db.session.remove()` — no pooled connection held across the Resend call,
   same discipline as the stream (`_publish_progress`, the comment above the
   stream).
4. `success` → `send_analysis_ready`; `error`/`timeout` → `send_analysis_failed`;
   `unlocked = unlock_method is not None`.

The whole helper is wrapped: nothing it does can raise out of the thread or
change the row. The voyage threads (`services/voyage/generation.py`) are not
touched.

### `services/demande_mail.py` (new)

`notify_if_visible(user) -> None` — mails every verified admin when `user` has
a `pending` CounselorProfile and `user.email_verified_at` is set. One send per
admin; one failure does not stop the others; zero verified admins logs a
warning. Fail-soft.

It is the moment a demande enters the admin queue
(`admin.list_counselor_applications` filters on the verified address). Called
from exactly three places, each after its own `commit()`:

| Call site | Condition |
|---|---|
| `counselor_space.apply()` | the applying user is already verified (the logged-in path) |
| `auth.verify_email()` | only on the `email_verified_at` None → set write — a second use of the link is a login and sends nothing |
| `auth.reset_password()` | only on the same None → set write (a reset also proves the inbox, spec 2026-09-29 decision 12) |

Since `email_verified_at` is written None → set at most once per account, and
a user holds at most one CounselorProfile, each demande mails the admins at
most once. Admin « Marquer comme vérifié » does not call it: the admin who
clicked is already in the dashboard.

### `routes/admin.py` — revoke

`revoke_counselor_application` calls `email_service.send_counselor_revoked`
after `db.session.commit()`, exactly as reject does. The 409 (not active) and
400 (no reason) paths send nothing.

### `routes/auth.py` — `reset_password`

After the commit: `email_service.send_password_changed(user)`, then
`demande_mail.notify_if_visible(user)` when this reset verified the address.
The password-changed mail neither checks nor stamps `auth_mail_sent_at`: it is
a security notice that follows a successful reset, and the reset link that
made it possible was itself paced by that clock. A refused password (400) or a
dead link sends nothing.

## Frontend

`frontend/src/app/analyse/en-cours/[id]/page.tsx` only.

- **While running:** the card's closing line « Laissez cet onglet ouvert, le
  rapport s'affiche automatiquement. » — which says the opposite — becomes
  « Le rapport s'affiche ici automatiquement. Vous recevrez un email quand il
  sera prêt — vous pouvez fermer cette page. »
- **Client give-up at `POLL_MAX_MS` (10 min):** a third state, separate from
  `error`. Eyebrow « Analyse en cours », heading « C'est plus long que
  prévu », text « Vous recevrez un email dès qu'elle sera prête. », button
  « Retour à mon espace » → `/espace`. Not « Nouvelle analyse »: the first run
  may still be going, and a second would cost a second generation.
- **Server `error` / `timeout`:** unchanged copy, unchanged « Nouvelle
  analyse » button.

## Errors

- Every builder catches everything, logs with the row/profile id where it can
  read one, and returns False. A mail failure never changes a status, an HTTP
  response code, or a committed write.
- No key (local dev): `send()` already logs « RESEND_API_KEY missing » and
  returns False; flows complete normally.
- Resend free plan is 100 mails/day, now shared by verification, reset,
  analysis outcome, revoke, demande and password-changed. Not acted on here;
  worth watching once real traffic starts.

## Testing

pytest, Resend mocked as in `tests/test_email_service.py`.

- **Builders:** recipient, subject, HTML and text parts present; prénom
  greeting with and without a profile; revoke reason HTML-escaped; the
  failure mail after an unlock carries the analysis id and no button; no
  builder body contains any report text; `send_counselor_revoked` returns
  False when its post-commit read raises.
- **`_mail` refactor:** verification and reset mails byte-identical to before.
- **`_run_analysis`:** success, error, timeout and no-active-prompt each call
  the right builder exactly once; `unlocked` follows `unlock_method`; an
  ownerless row and an unverified owner send nothing (a deleted owner takes
  the same `user is None` branch — the foreign key keeps it from existing);
  a builder that raises leaves the written status as it was.
- **Demande:** verified applicant via `apply` → admins mailed; new-account
  `apply` → nothing until `verify_email`, then exactly one round; second
  `verify_email` → nothing; `reset_password` that verifies → mailed; reset of
  an already-verified account → no demande mail; approved/rejected/revoked
  profile → nothing; two admins → two sends, one failing does not stop the
  other; unverified admin skipped; zero admins → warning, no raise.
- **Revoke:** mail after commit; 409 and 400 paths send nothing.
- **Password changed:** sent on success; not on a refused password or a dead
  link; `auth_mail_sent_at` unchanged.
- **Waiting page:** E2E on `http://localhost:8080` — running line visible;
  forced give-up shows « C'est plus long que prévu » and the espace button —
  unless planning finds a frontend test runner to cover it.

## Docs

CLAUDE.md gains a short « Mails transactionnels » list under « Email
verification »: each mail, its trigger, and the two rules (send after commit;
no content in a mail).

## Out of scope

Found on 2026-10-01, flagged, not fixed by this spec:

- A paid unlock whose regeneration fails is a dead end (409 on retry); this
  spec only gives the candidate a reply path.
- `queued` rows are never reaped.
- `reap_stale_running` keys on `created_at`, so a paid regeneration
  interrupted by a restart is wrongly marked `error` — and gets no failure mail,
  since the reaper is not a generation exit.
- No payment record table.
- `/confidentialite` RGPD contact « [À COMPLÉTER] »; footer bonjour@ vs site
  nneoori@proton.me.
- Plain-text parts for the approved/rejected mails.

## Amendments (planning, 2026-10-02)

Found while writing the implementation plan
(`docs/superpowers/plans/2026-10-02-transactional-mails.md`), against the code:

1. **Waiting page line.** The running card already ended with « Laissez cet
   onglet ouvert, le rapport s'affiche automatiquement. » — the opposite of
   the new line. The new copy replaces it instead of being added under the
   subtitle (Frontend, above).
2. **`_mail` has no `quote=` keyword.** The revocation reason sits between two
   paragraphs, which a keyword cannot place; a `_Quote(...)` paragraph does.
3. **`unlocked`, not `paid`.** A first run can already be on the paid tier
   (`FORCE_ANALYSIS_TIER` defaults to `paid`); the second wording belongs to
   the run an unlock starts, which is what `unlock_method` marks.
4. **`send_new_demande(admin)` takes the admin's `User`**, so the admin mail
   greets by prénom like the others.
