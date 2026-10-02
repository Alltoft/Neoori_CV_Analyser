# Mails transactionnels, lot 2 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Five new transactional mails — analysis ready, analysis failed, new conseiller demande (to the admins), conseiller revoked, password changed — plus two honest lines on the analysis waiting page.

**Architecture:** Every mail is a fail-soft builder in `backend/app/services/email_service.py`, rendered into HTML + plain text by one paragraph-list helper (`_mail`). Each builder is called explicitly, right after the commit that decides it: the generation thread's final status (`anthropic_service._notify_outcome`), the admin revoke route, the reset route, and — for the admin mail — a small new `services/demande_mail.py`, called from the three places a demande enters the admin queue. The frontend change is copy plus one extra state on one page.

**Tech Stack:** Flask 3.1, Flask-SQLAlchemy 3.1 (SQLAlchemy 2.0), Resend SDK 2.30, pytest on SQLite in-memory; Next.js 16 / React 19 client component.

**Spec:** `docs/superpowers/specs/2026-10-02-transactional-mails-design.md` — amended while planning (next section). Read it alongside this plan.

## Spec amendments made while planning

Four details in the spec did not fit the code. The spec file is corrected in the same commit as this plan:

1. **Waiting page.** The running card already ends with « Laissez cet onglet ouvert, le rapport s'affiche automatiquement. » — the opposite of the new line. The new copy *replaces* that line rather than being added under the subtitle: « Le rapport s'affiche ici automatiquement. Vous recevrez un email quand il sera prêt — vous pouvez fermer cette page. »
2. **`_mail` has no `quote=` keyword.** The revocation reason sits *between* two paragraphs, which a keyword cannot place. A paragraph wrapped in `_Quote(...)` renders in the grey box instead.
3. **`unlocked`, not `paid`.** A first run can already be on the paid tier (`FORCE_ANALYSIS_TIER` defaults to `paid`); the different wording belongs to the *second* run an unlock starts, which is what `unlock_method` marks.
4. **`send_new_demande(admin)` takes the admin's `User`**, so it can greet by prénom like the other mails.

## Global Constraints

- App UI and mail copy: French. Code comments and commit messages: English.
- Mail copy is the spec's « Mails » section, verbatim. Mail strings use straight apostrophes (as the existing mails do); the waiting page's JSX text uses typographic ’ (as that page already does).
- UI copy never uses: boussole, copilote, miroir, révélation, épanouissement, alignement, excellence, talent unique, vous vous démarquez.
- Send after the commit that decided it. Fail-soft: a builder logs and returns `False`, never raises; a mail failure never changes a status, an HTTP response code, or a committed write.
- No content in any mail: no report text, no voyage text, no applicant data.
- No mail to an address nobody proved: every recipient has `email_verified_at` set; legacy anonymous analyses (`user_id` NULL) get nothing.
- HTML and plain-text parts from one paragraph list; footer « neoori — pour nous écrire, répondez à ce message. »; sender `MAIL_FROM`; links from `APP_URL`.
- Do not touch `send_counselor_approved` / `send_counselor_rejected`, the voyage threads (`services/voyage/generation.py`), the reapers in `app/__init__.py`, or `services/unlock_service.py` — the unlock dead end is out of scope.
- No migration, no new dependency, no new environment variable.
- Every commit message ends with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

Inputs and conditions the spec implies but does not test, most likely to bite first. Each has a test in the task that owns the code:

1. **A prénom made of spaces** → « Bonjour, », never « Bonjour   , ». *(Task 1: `test_a_blank_prenom_greets_without_a_name`)*
2. **An unlocked regeneration that dies at the « Aucun prompt actif » exit** → the unlock failure mail with its reference, not « relancez une analyse ». *(Task 3: `test_an_unlocked_run_with_no_active_prompt_asks_for_a_reply`)*
3. **The admin lookup failing while an applicant verifies** → the verification still answers 200 and signs them in. *(Task 5: `test_a_failed_admin_lookup_does_not_block_the_verification`)*
4. **Resend down during a reset or a revoke** → the password still changes, the access is still withdrawn, the response is still 200. *(Task 4: `test_a_reset_survives_a_mail_outage`, `test_a_mail_failure_does_not_undo_the_revocation`)*
5. **Reloading the waiting page after the 10-minute give-up** → polling starts again and a finished run opens the report: the give-up is not sticky. *(Task 7: E2E step 3)*

## Execution notes

- Work in the **main checkout** on branch `feat/transactional-mails` (created with the spec, commit 1cbb944) — not a worktree. Task 7's dev stack bind-mounts `./backend` and `./frontend` from this directory.
- Backend tests: `cd backend && ./venv/bin/python -m pytest -q -p no:cacheprovider <paths>`. Baseline on this branch: **1151 passed**.
- `frontend/src/app/analyse/en-cours/[id]/page.tsx` already has one ESLint error, `react-hooks/purity` on `useRef(Date.now())`. It is not ours — do not fix it here.
- Task 7's E2E needs Docker and a browser (Claude in Chrome). Run it from the main session, not from a subagent.

## File map

| File | Change | Task |
|---|---|---|
| `backend/app/services/email_service.py` | `_mail`, `_Quote`, `_greeting`, `prenom_of` replace `_link_mail` / `_prenom`; five new builders | 1, 2 |
| `backend/app/services/anthropic_service.py` | `_notify_outcome()` after each final commit of `_run_analysis` | 3 |
| `backend/app/routes/admin.py` | revoke sends `send_counselor_revoked` | 4 |
| `backend/app/routes/auth.py` | reset sends `send_password_changed`; verify and reset call `demande_mail` on an address's first proof | 4, 5 |
| `backend/app/services/demande_mail.py` *(new)* | `notify_if_visible(user)` — the admin fan-out | 5 |
| `backend/app/routes/counselor_space.py` | `apply()` calls `demande_mail` for a signed-in applicant | 5 |
| `frontend/src/app/analyse/en-cours/[id]/page.tsx` | the running line; a `stalled` state at the 10-minute give-up | 6 |
| `CLAUDE.md` | « Mails transactionnels » section | 7 |
| `backend/tests/test_transactional_mails.py` *(new)* | renderer + builders | 1, 2 |
| `backend/tests/test_analysis_outcome_mail.py` *(new)* | the generation thread's mail | 3 |
| `backend/tests/test_counselor_review.py`, `backend/tests/test_auth_link_routes.py` | revoke and reset mails | 4 |
| `backend/tests/test_demande_mail.py` *(new)* | the admin fan-out and its three doors | 5 |

---

### Task 1: One renderer for every mail

**Files:**
- Modify: `backend/app/services/email_service.py` — `_layout` docstring; replace `_link_mail` and `_prenom`; `send_verification`; `send_password_reset`
- Create: `backend/tests/test_transactional_mails.py`

**Interfaces:**
- Consumes: the existing `_button(href, label)`, `FOOTER`, `Profile` in `email_service.py`.
- Produces (module `app.services.email_service`):
  - `class _Quote(str)` — a paragraph `_mail` renders in the grey box
  - `_mail(paragraphs: list[str], *, button: tuple[str, str] | None = None, small: str | None = None) -> tuple[str, str]` — returns `(html_body, text)`; `button` is `(label, href)`
  - `_greeting(prenom: str) -> str` — `"Bonjour Marie,"`, or `"Bonjour,"` for `""`
  - `prenom_of(user) -> str` — the stripped profile prénom, or `""`. Public: Task 3 calls it from the generation thread.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_transactional_mails.py`:

```python
"""Mails transactionnels, lot 2 (spec 2026-10-02): the renderer every mail
shares, and the builders that use it."""
from unittest.mock import patch

from app.extensions import db
from app.models.profile import Profile
from app.services import email_service
from app.services.email_service import FOOTER, _greeting, _mail, _Quote, prenom_of

SEND = "app.services.email_service.resend.Emails.send"

BUTTON_HTML = (
    '<p style="margin:24px 0"><a href="https://x.fr/v?token=abc" style="background:#c96442;'
    "color:#ffffff;padding:12px 20px;border-radius:8px;text-decoration:none;"
    'display:inline-block">Confirmer</a></p>'
)


def _sent(mock_send) -> dict:
    return mock_send.call_args[0][0]


# ── the renderer ─────────────────────────────────────────────────────────────

def test_the_account_mails_render_byte_for_byte_as_before():
    """Captured from _link_mail on 2026-10-02, before it became _mail: the
    verification and reset mails must not move by a character."""
    body, text = _mail(
        ["Bonjour Marie,", "Ligne <2> & fin."],
        button=("Confirmer", "https://x.fr/v?token=abc"),
        small="Petit texte.",
    )
    assert body == (
        "<p>Bonjour Marie,</p><p>Ligne &lt;2&gt; &amp; fin.</p>"
        + BUTTON_HTML
        + '<p style="font-size:13px">Petit texte.</p>'
    )
    assert text == (
        "Bonjour Marie,\n\nLigne <2> & fin.\n\nhttps://x.fr/v?token=abc\n\n"
        "Petit texte.\n\nneoori — pour nous écrire, répondez à ce message.\n"
    )


def test_a_mail_without_button_or_small_print_ends_on_the_footer():
    body, text = _mail(["Un.", "Deux."])
    assert body == "<p>Un.</p><p>Deux.</p>"
    assert text == f"Un.\n\nDeux.\n\n{FOOTER}\n"


def test_a_quote_sits_in_the_grey_box_escaped():
    body, text = _mail(["Avant.", _Quote('<b>x</b> & "y"'), "Après."])
    assert body == (
        "<p>Avant.</p>"
        '<p style="padding:12px;background:#f3eee2;border-radius:8px">'
        '&lt;b&gt;x&lt;/b&gt; &amp; "y"</p>'
        "<p>Après.</p>"
    )
    # The text form has no box: the words stand as their own paragraph.
    assert text == f'Avant.\n\n<b>x</b> & "y"\n\nAprès.\n\n{FOOTER}\n'


def test_the_greeting_has_no_name_slot_without_a_prenom():
    assert _greeting("Marie") == "Bonjour Marie,"
    assert _greeting("") == "Bonjour,"


def test_prenom_of_reads_the_profile_and_strips_it(app, make_user):
    user = make_user()
    assert prenom_of(user) == ""          # no profile row at all
    db.session.add(Profile(user_id=user.id, prenom="  Marie "))
    db.session.commit()
    assert prenom_of(user) == "Marie"


def test_a_blank_prenom_greets_without_a_name(app, make_user):
    # Review Focus 1: a prénom of spaces must not give « Bonjour    , ».
    app.config["RESEND_API_KEY"] = "re_test"
    user = make_user(verified=False)
    db.session.add(Profile(user_id=user.id, prenom="   "))
    db.session.commit()
    with patch(SEND, return_value={"id": "1"}) as mock_send:
        email_service.send_verification(user)
    assert _sent(mock_send)["text"].startswith("Bonjour,\n\n")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && ./venv/bin/python -m pytest -q -p no:cacheprovider tests/test_transactional_mails.py`
Expected: collection ERROR — `ImportError: cannot import name '_greeting' from 'app.services.email_service'`.

- [ ] **Step 3: Implement the renderer**

In `backend/app/services/email_service.py`:

(a) In `_layout`, replace the docstring line

```python
    """One sober frame for both mails. Inline styles: mail clients drop <style>."""
```

with

```python
    """One sober frame for every mail. Inline styles: mail clients drop <style>."""
```

(b) Replace the whole of `_link_mail` and `_prenom` — this block:

```python
def _link_mail(paragraphs: list[str], label: str, link: str, small: str) -> tuple[str, str]:
    """The HTML body and the plain-text body of an account mail, built from one
    copy so a wording edit cannot reach one form and miss the other. Paragraphs
    are plain text: escaped here for the HTML form only."""
    def esc(s: str) -> str:
        return html_escape.escape(s, quote=False)

    body = (
        "".join(f"<p>{esc(p)}</p>" for p in paragraphs)
        + _button(link, label)
        + f'<p style="font-size:13px">{esc(small)}</p>'
    )
    text = "\n\n".join(paragraphs) + f"\n\n{link}\n\n{small}\n\n{FOOTER}\n"
    return body, text


def _prenom(user) -> str:
    profile = Profile.query.filter_by(user_id=user.id).first()
    return (profile.prenom or "").strip() if profile else ""
```

with:

```python
class _Quote(str):
    """A paragraph _mail() sets in the grey box: someone else's words, such as
    an admin's reason. Escaped like every paragraph; plain in the text form."""


_QUOTE_STYLE = "padding:12px;background:#f3eee2;border-radius:8px"


def _mail(
    paragraphs: list[str],
    *,
    button: tuple[str, str] | None = None,
    small: str | None = None,
) -> tuple[str, str]:
    """The HTML body and the plain-text body of a mail, built from one copy so
    a wording edit cannot reach one form and miss the other. Paragraphs are
    plain text, escaped here for the HTML form only; a _Quote one goes in the
    grey box. `button` is (label, href): the text form prints the bare href."""
    def esc(s: str) -> str:
        return html_escape.escape(s, quote=False)

    body = "".join(
        f'<p style="{_QUOTE_STYLE}">{esc(p)}</p>' if isinstance(p, _Quote) else f"<p>{esc(p)}</p>"
        for p in paragraphs
    )
    parts = list(paragraphs)
    if button is not None:
        label, href = button
        body += _button(href, label)
        parts.append(href)
    if small is not None:
        body += f'<p style="font-size:13px">{esc(small)}</p>'
        parts.append(small)
    parts.append(FOOTER)
    return body, "\n\n".join(parts) + "\n"


def _greeting(prenom: str) -> str:
    return f"Bonjour {prenom}," if prenom else "Bonjour,"


def prenom_of(user) -> str:
    """The prénom on the person's profile, or "" when there is none. Public:
    the generation thread reads it before it releases its DB connection."""
    profile = Profile.query.filter_by(user_id=user.id).first()
    return (profile.prenom or "").strip() if profile else ""
```

(c) In `send_verification`, replace:

```python
        prenom = _prenom(user)
        body, text = _link_mail(
            [
                f"Bonjour {prenom}," if prenom else "Bonjour,",
                "Pour activer votre compte neoori, confirmez votre adresse : ouvrez le "
                "lien ci-dessous puis saisissez votre mot de passe. Il est valable 48 heures.",
            ],
            "Confirmer mon adresse", link,
            "Si vous n'avez pas créé de compte, ignorez ce message.",
        )
```

with:

```python
        body, text = _mail(
            [
                _greeting(prenom_of(user)),
                "Pour activer votre compte neoori, confirmez votre adresse : ouvrez le "
                "lien ci-dessous puis saisissez votre mot de passe. Il est valable 48 heures.",
            ],
            button=("Confirmer mon adresse", link),
            small="Si vous n'avez pas créé de compte, ignorez ce message.",
        )
```

(d) In `send_password_reset`, replace:

```python
        body, text = _link_mail(
            [
                "Une demande de réinitialisation a été faite pour votre compte. Le lien "
                "est valable 1 heure et ne sert qu'une fois.",
            ],
            "Choisir un nouveau mot de passe", link,
            "Si vous n'êtes pas à l'origine de cette demande, ignorez ce message : "
            "votre mot de passe reste inchangé.",
        )
```

with:

```python
        body, text = _mail(
            [
                "Une demande de réinitialisation a été faite pour votre compte. Le lien "
                "est valable 1 heure et ne sert qu'une fois.",
            ],
            button=("Choisir un nouveau mot de passe", link),
            small="Si vous n'êtes pas à l'origine de cette demande, ignorez ce message : "
            "votre mot de passe reste inchangé.",
        )
```

- [ ] **Step 4: Run the new tests and every suite that renders the account mails**

Run: `cd backend && ./venv/bin/python -m pytest -q -p no:cacheprovider tests/test_transactional_mails.py tests/test_auth_mail.py tests/test_email_service.py tests/test_auth_link_routes.py tests/test_counselor_apply.py`
Expected: all pass.

Run: `cd backend && grep -rn "_link_mail\|_prenom(" app`
Expected: no output.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/email_service.py backend/tests/test_transactional_mails.py
git commit -m "refactor(mail): one renderer for every mail's HTML and text

_link_mail becomes _mail: an optional button, optional small print, and
_Quote paragraphs in the grey box, so the next mails can share it. The
verification and reset mails render byte for byte as before.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: The five new builders

**Files:**
- Modify: `backend/app/services/email_service.py` — append after `send_password_reset`
- Test: `backend/tests/test_transactional_mails.py` — add imports, append tests

**Interfaces:**
- Consumes: Task 1's `_mail`, `_Quote`, `_greeting`, `prenom_of`; the existing `send`, `_layout`, `_app_url`, `CounselorProfile` import.
- Produces (module `app.services.email_service`):
  - `send_analysis_ready(to: str, prenom: str, *, unlocked: bool) -> bool`
  - `send_analysis_failed(to: str, prenom: str, *, unlocked: bool, analysis_id: str) -> bool`
  - `send_new_demande(admin) -> bool` — `admin` is a `User`
  - `send_counselor_revoked(profile: CounselorProfile) -> bool`
  - `send_password_changed(user) -> bool`

  Every builder calls `send(to, subject, html, text)` with **four positional arguments** (Task 4's route tests unpack `call_args[0]` that way), and returns `False` instead of raising.

- [ ] **Step 1: Write the failing tests**

In `backend/tests/test_transactional_mails.py`, extend the imports at the top so they read:

```python
from datetime import datetime
from unittest.mock import patch

from app.extensions import db
from app.models.counselor_profile import CounselorProfile
from app.models.profile import Profile
from app.models.user import User
from app.services import email_service
from app.services.email_service import FOOTER, _greeting, _mail, _Quote, prenom_of
```

Then append at the end of the file:

```python
# ── the five new mails ───────────────────────────────────────────────────────

def _revoked_profile(reason: str) -> CounselorProfile:
    user = User(email="conseiller@capemploi.fr", password_hash="x", role="candidate",
                email_verified_at=datetime.utcnow())
    db.session.add(user)
    db.session.commit()
    profile = CounselorProfile(
        user_id=user.id, structure="Cap Emploi 31", fonction="Conseillère",
        telephone="0561000000", status="revoked", decision_reason=reason,
    )
    db.session.add(profile)
    db.session.commit()
    return profile


def test_the_ready_mail_links_to_the_espace(app):
    app.config["RESEND_API_KEY"] = "re_test"
    app.config["APP_URL"] = "https://neoori.tech"
    with patch(SEND, return_value={"id": "1"}) as mock_send:
        assert email_service.send_analysis_ready("marie@test.fr", "Marie", unlocked=False) is True
    mail = _sent(mock_send)
    assert mail["to"] == ["marie@test.fr"]
    assert mail["subject"] == "Votre analyse est prête"
    assert mail["text"].startswith(
        "Bonjour Marie,\n\nVotre analyse est prête. Elle est enregistrée dans votre espace.\n\n"
    )
    assert 'href="https://neoori.tech/espace"' in mail["html"]
    assert "Ouvrir mon espace" in mail["html"]
    assert "https://neoori.tech/espace" in mail["text"]


def test_the_ready_mail_after_an_unlock_says_complete(app):
    app.config["RESEND_API_KEY"] = "re_test"
    with patch(SEND, return_value={"id": "1"}) as mock_send:
        email_service.send_analysis_ready("marie@test.fr", "", unlocked=True)
    mail = _sent(mock_send)
    assert mail["subject"] == "Votre analyse complète est prête"
    assert mail["text"].startswith(
        "Bonjour,\n\nLa version complète de votre analyse est prête. Elle remplace "
        "la version précédente dans votre espace.\n\n"
    )
    assert "/espace" in mail["html"]


def test_the_failure_mail_sends_the_candidate_back_to_the_espace(app):
    app.config["RESEND_API_KEY"] = "re_test"
    with patch(SEND, return_value={"id": "1"}) as mock_send:
        email_service.send_analysis_failed("marie@test.fr", "Marie", unlocked=False, analysis_id="a-1")
    mail = _sent(mock_send)
    assert mail["subject"] == "Votre analyse n'a pas abouti"
    assert (
        "La génération de votre analyse n'a pas abouti. Vous pouvez relancer "
        "une analyse depuis votre espace."
    ) in mail["text"]
    assert "/espace" in mail["html"]
    assert "Référence" not in mail["text"]


def test_the_failure_mail_after_an_unlock_asks_for_a_reply(app):
    """The unlock dead end (a second unlock is a 409) stays in code: this mail
    is the way out, through the reply address, with the row id to find it by."""
    app.config["RESEND_API_KEY"] = "re_test"
    with patch(SEND, return_value={"id": "1"}) as mock_send:
        email_service.send_analysis_failed("marie@test.fr", "Marie", unlocked=True, analysis_id="a-1")
    mail = _sent(mock_send)
    assert mail["subject"] == "Le déblocage de votre analyse n'a pas abouti"
    assert (
        "Votre déblocage est bien enregistré, mais la version complète n'a pas "
        "pu être générée. Répondez à ce message : nous la relançons pour vous."
    ) in mail["text"]
    assert "Référence : a-1" in mail["text"]
    assert "Référence : a-1" in mail["html"]
    assert "<a " not in mail["html"]      # no button: the espace offers nothing here


def test_the_demande_mail_greets_the_admin_and_links_to_the_queue(app, make_user):
    app.config["RESEND_API_KEY"] = "re_test"
    app.config["APP_URL"] = "https://neoori.tech"
    admin = make_user(email="admin@neoori.tech", role="admin")
    db.session.add(Profile(user_id=admin.id, prenom="Paul"))
    db.session.commit()
    with patch(SEND, return_value={"id": "1"}) as mock_send:
        assert email_service.send_new_demande(admin) is True
    mail = _sent(mock_send)
    assert mail["to"] == ["admin@neoori.tech"]
    assert mail["subject"] == "Nouvelle demande de compte conseiller"
    assert mail["text"].startswith(
        "Bonjour Paul,\n\nUne demande de compte conseiller attend votre décision.\n\n"
    )
    assert 'href="https://neoori.tech/admin/conseillers"' in mail["html"]


def test_the_revocation_mail_carries_the_reason_escaped(app):
    app.config["RESEND_API_KEY"] = "re_test"
    profile = _revoked_profile('<b>x</b> & "y"')
    with patch(SEND, return_value={"id": "1"}) as mock_send:
        assert email_service.send_counselor_revoked(profile) is True
    mail = _sent(mock_send)
    assert mail["to"] == ["conseiller@capemploi.fr"]
    assert mail["subject"] == "Votre accès conseiller"
    assert "&lt;b&gt;x&lt;/b&gt; &amp;" in mail["html"]
    assert "<b>" not in mail["html"]
    assert mail["text"] == (
        "Bonjour,\n\nVotre accès conseiller a été retiré.\n\n"
        '<b>x</b> & "y"\n\n'
        "Les codes que vous avez déjà remis restent valables. Votre compte reste "
        "utilisable comme compte candidat.\n\n"
        "neoori — pour nous écrire, répondez à ce message.\n"
    )


def test_the_revocation_mail_fails_soft_on_a_post_commit_read(app):
    class _Lost:
        """A profile whose post-commit reload dies, as a dropped connection would."""
        id = "p-1"

        @property
        def user(self):
            raise RuntimeError("Lost connection to MySQL server during query")

    assert email_service.send_counselor_revoked(_Lost()) is False


def test_the_password_changed_mail_points_at_a_new_reset(app, make_user):
    app.config["RESEND_API_KEY"] = "re_test"
    app.config["APP_URL"] = "https://neoori.tech"
    user = make_user(email="marie@test.fr")
    db.session.add(Profile(user_id=user.id, prenom="Marie"))
    db.session.commit()
    with patch(SEND, return_value={"id": "1"}) as mock_send:
        assert email_service.send_password_changed(user) is True
    mail = _sent(mock_send)
    assert mail["to"] == ["marie@test.fr"]
    assert mail["subject"] == "Votre mot de passe a été modifié"
    assert mail["text"].startswith(
        "Bonjour Marie,\n\n"
        "Le mot de passe de votre compte neoori vient d'être modifié.\n\n"
        "Si c'est vous, il n'y a rien à faire.\n\n"
        "Si vous n'êtes pas à l'origine de ce changement, choisissez-en un nouveau "
        "tout de suite.\n\n"
    )
    assert 'href="https://neoori.tech/mot-de-passe-oublie"' in mail["html"]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && ./venv/bin/python -m pytest -q -p no:cacheprovider tests/test_transactional_mails.py`
Expected: the 8 new tests FAIL with `AttributeError: module 'app.services.email_service' has no attribute 'send_analysis_ready'` (and the same for the other four builders); Task 1's 6 tests still pass.

- [ ] **Step 3: Implement the builders**

Append to the end of `backend/app/services/email_service.py`:

```python
# ── Lot 2 (transactional mails spec, 2026-10-02) ─────────────────────────────
# Each one leaves after the commit that decided it and says that something
# happened and where to read it, behind a login — never the content itself.


def send_analysis_ready(to: str, prenom: str, *, unlocked: bool) -> bool:
    """« Votre analyse est prête ». Plain values, not rows: the generation
    thread releases its DB connection before calling this. `unlocked` is the
    row's second run, started by a payment or a code (unlock_method set)."""
    try:
        if unlocked:
            subject, title = "Votre analyse complète est prête", "Analyse complète prête"
            line = (
                "La version complète de votre analyse est prête. Elle remplace la "
                "version précédente dans votre espace."
            )
        else:
            subject, title = "Votre analyse est prête", "Analyse prête"
            line = "Votre analyse est prête. Elle est enregistrée dans votre espace."
        body, text = _mail(
            [_greeting(prenom), line],
            button=("Ouvrir mon espace", f"{_app_url()}/espace"),
        )
        return send(to, subject, _layout(title, body), text)
    except Exception:
        current_app.logger.exception("Could not build/send the analysis-ready mail.")
        return False


def send_analysis_failed(to: str, prenom: str, *, unlocked: bool, analysis_id: str) -> bool:
    """« Votre analyse n'a pas abouti ». After an unlock the espace has nothing
    to offer — a second unlock is a 409 — so that variant asks for a reply and
    carries the row id to find it by. Relaunching it is the team's job."""
    try:
        if unlocked:
            subject, title = "Le déblocage de votre analyse n'a pas abouti", "Déblocage interrompu"
            body, text = _mail([
                _greeting(prenom),
                "Votre déblocage est bien enregistré, mais la version complète n'a pas pu "
                "être générée. Répondez à ce message : nous la relançons pour vous.",
                f"Référence : {analysis_id}",
            ])
        else:
            subject, title = "Votre analyse n'a pas abouti", "Analyse interrompue"
            body, text = _mail(
                [
                    _greeting(prenom),
                    "La génération de votre analyse n'a pas abouti. Vous pouvez relancer "
                    "une analyse depuis votre espace.",
                ],
                button=("Ouvrir mon espace", f"{_app_url()}/espace"),
            )
        return send(to, subject, _layout(title, body), text)
    except Exception:
        current_app.logger.exception(
            "Could not build/send the analysis-failed mail for %s.", analysis_id
        )
        return False


def send_new_demande(admin) -> bool:
    """« Nouvelle demande de compte conseiller », to one admin. Nothing about
    the applicant: name, structure and phone stay behind the dashboard login."""
    try:
        body, text = _mail(
            [
                _greeting(prenom_of(admin)),
                "Une demande de compte conseiller attend votre décision.",
            ],
            button=("Voir les demandes", f"{_app_url()}/admin/conseillers"),
        )
        return send(
            admin.email, "Nouvelle demande de compte conseiller",
            _layout("Nouvelle demande", body), text,
        )
    except Exception:
        current_app.logger.exception("Could not build/send the new-demande mail.")
        return False


def send_counselor_revoked(profile: CounselorProfile) -> bool:
    # Same reasoning as send_counselor_approved above: profile.user and
    # profile.decision_reason are post-commit reads that can themselves fail.
    # The reason is already shown on /conseiller; the mail discloses nothing new.
    try:
        user = profile.user
        body, text = _mail([
            _greeting(prenom_of(user)),
            "Votre accès conseiller a été retiré.",
            _Quote(profile.decision_reason or ""),
            "Les codes que vous avez déjà remis restent valables. Votre compte reste "
            "utilisable comme compte candidat.",
        ])
        return send(
            user.email, "Votre accès conseiller",
            _layout("Accès conseiller retiré", body), text,
        )
    except Exception:
        # profile.id is itself an expired post-commit attribute -- fall back
        # rather than let the logging call raise.
        try:
            profile_id = profile.id
        except Exception:
            profile_id = "?"
        current_app.logger.exception(
            "Could not build/send the revocation mail for profile %s.", profile_id
        )
        return False


def send_password_changed(user) -> bool:
    """« Votre mot de passe a été modifié », after a reset. Neither checks nor
    stamps auth_mail_sent_at: it follows a reset whose link that clock already
    paced, and it must reach the owner even when someone else held the link."""
    try:
        body, text = _mail(
            [
                _greeting(prenom_of(user)),
                "Le mot de passe de votre compte neoori vient d'être modifié.",
                "Si c'est vous, il n'y a rien à faire.",
                "Si vous n'êtes pas à l'origine de ce changement, choisissez-en un "
                "nouveau tout de suite.",
            ],
            button=("Choisir un nouveau mot de passe", f"{_app_url()}/mot-de-passe-oublie"),
        )
        return send(
            user.email, "Votre mot de passe a été modifié",
            _layout("Mot de passe modifié", body), text,
        )
    except Exception:
        current_app.logger.exception("Could not build/send the password-changed mail.")
        return False
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && ./venv/bin/python -m pytest -q -p no:cacheprovider tests/test_transactional_mails.py tests/test_email_service.py tests/test_auth_mail.py`
Expected: all pass (14 in `test_transactional_mails.py`).

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/email_service.py backend/tests/test_transactional_mails.py
git commit -m "feat(mail): the five new transactional mails

Analysis ready and failed (each with an after-unlock wording), new demande
to an admin, conseiller revoked, password changed. Built and tested here;
nothing sends them yet.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Mail the owner when a run ends

**Files:**
- Modify: `backend/app/services/anthropic_service.py` — imports; the three final exits of `_run_analysis`; new `_notify_outcome` between `_run_analysis` and `start_analysis`
- Create: `backend/tests/test_analysis_outcome_mail.py`

**Interfaces:**
- Consumes: Task 2's `email_service.send_analysis_ready(to, prenom, *, unlocked)` and `email_service.send_analysis_failed(to, prenom, *, unlocked, analysis_id)`; Task 1's `email_service.prenom_of(user)`. Call them **through the module** (`email_service.send_analysis_ready(...)`), never `from .email_service import ...`, or the tests' `patch("app.services.email_service.send_analysis_ready")` cannot reach them.
- Produces: `_notify_outcome(analysis_id: str) -> None` (module-private).

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_analysis_outcome_mail.py`:

```python
"""The analysis outcome mail (transactional mails spec, 2026-10-02).

Every finished run mails its owner — ready or failed, first run or the second
one an unlock starts — after the row is committed, without report text, and
never at the cost of the status it reports on.
"""
from unittest.mock import MagicMock, patch

import pytest

from app.extensions import db
from app.models.analysis import Analysis
from app.models.profile import Profile
from app.models.prompt_version import PromptVersion
from app.services import anthropic_service as svc
from app.services.anthropic_service import _section_keys

READY = "app.services.email_service.send_analysis_ready"
FAILED = "app.services.email_service.send_analysis_failed"
SEND = "app.services.email_service.resend.Emails.send"

# Written into every section of the streamed report, so a test can prove it
# never reaches a mail.
MARKER = "MARQUEUR-DU-RAPPORT"


def _queued(user=None, *, unlock_method=None, prompt=True, tier="free") -> str:
    if prompt:
        db.session.add(PromptVersion(version_label="test", system_prompt_text="x",
                                     is_active=True, path="1"))
    analysis = Analysis(
        user_id=user.id if user is not None else None,
        inputs={"_path": "1", "_tier": tier, "cv_text": "c" * 300, "cible_visee": "t" * 60},
        status="queued",
        unlock_method=unlock_method,
    )
    db.session.add(analysis)
    db.session.commit()
    return analysis.id


def _streaming_client(tier="free"):
    """A client whose stream writes every section of the tier."""
    chunks = [f'"{k}": {{"title": "T", "body_markdown": "{MARKER}", "items": []}},'
              for k in _section_keys("1", tier)]
    stream = MagicMock()
    stream.__enter__.return_value = stream
    stream.text_stream = iter(["{"] + chunks)
    stream.get_final_message.return_value = MagicMock(
        usage=MagicMock(input_tokens=100, output_tokens=200))
    client = MagicMock()
    client.messages.stream.return_value = stream
    return client


def _failing_client(message: str):
    client = MagicMock()
    client.messages.stream.side_effect = RuntimeError(message)
    return client


def _run(app, analysis_id, client) -> None:
    with patch.object(svc, "_get_client", return_value=client):
        svc._run_analysis(analysis_id, app)


def _row(analysis_id) -> Analysis:
    # The run committed from its own app context; this one still holds the
    # objects it created.
    db.session.expire_all()
    return db.session.get(Analysis, analysis_id)


def test_a_finished_analysis_mails_its_owner(app, make_user):
    user = make_user(email="marie@test.fr")
    aid = _queued(user)
    with patch(READY) as ready, patch(FAILED) as failed:
        _run(app, aid, _streaming_client())
    assert _row(aid).status == "success"
    ready.assert_called_once_with("marie@test.fr", "", unlocked=False)
    failed.assert_not_called()


def test_the_run_an_unlock_starts_says_complete(app, make_user):
    user = make_user(email="marie@test.fr")
    aid = _queued(user, unlock_method="payment", tier="paid")
    with patch(READY) as ready:
        _run(app, aid, _streaming_client("paid"))
    ready.assert_called_once_with("marie@test.fr", "", unlocked=True)


@pytest.mark.parametrize("message, status", [
    ("boom", "error"),
    ("Request timed out.", "timeout"),
])
def test_a_failed_run_mails_the_failure(app, make_user, message, status):
    user = make_user(email="marie@test.fr")
    aid = _queued(user)
    with patch(READY) as ready, patch(FAILED) as failed:
        _run(app, aid, _failing_client(message))
    assert _row(aid).status == status
    failed.assert_called_once_with("marie@test.fr", "", unlocked=False, analysis_id=aid)
    ready.assert_not_called()


def test_no_active_prompt_mails_the_failure(app, make_user):
    user = make_user(email="marie@test.fr")
    aid = _queued(user, prompt=False)
    client = _streaming_client()
    with patch(FAILED) as failed:
        _run(app, aid, client)
    assert _row(aid).status == "error"
    client.messages.stream.assert_not_called()
    failed.assert_called_once_with("marie@test.fr", "", unlocked=False, analysis_id=aid)


def test_an_unlocked_run_with_no_active_prompt_asks_for_a_reply(app, make_user):
    # Review Focus 2: the early exit strands an unlocked row just the same.
    app.config["RESEND_API_KEY"] = "re_test"
    user = make_user(email="marie@test.fr")
    aid = _queued(user, unlock_method="code", prompt=False)
    with patch(SEND, return_value={"id": "1"}) as mock_send:
        _run(app, aid, _streaming_client())
    mail = mock_send.call_args[0][0]
    assert mail["subject"] == "Le déblocage de votre analyse n'a pas abouti"
    assert f"Référence : {aid}" in mail["text"]


def test_an_ownerless_analysis_mails_nobody(app):
    aid = _queued(None)
    with patch(READY) as ready:
        _run(app, aid, _streaming_client())
    assert _row(aid).status == "success"
    ready.assert_not_called()


def test_an_unproven_address_gets_nothing(app, make_user):
    aid = _queued(make_user(verified=False))
    with patch(READY) as ready:
        _run(app, aid, _streaming_client())
    ready.assert_not_called()


def test_the_mail_carries_the_prenom_and_no_report_text(app, make_user):
    app.config["RESEND_API_KEY"] = "re_test"
    user = make_user(email="marie@test.fr")
    db.session.add(Profile(user_id=user.id, prenom="Marie"))
    db.session.commit()
    aid = _queued(user)
    with patch(SEND, return_value={"id": "1"}) as mock_send:
        _run(app, aid, _streaming_client())
    mail = mock_send.call_args[0][0]
    assert mail["text"].startswith("Bonjour Marie,\n\n")
    assert MARKER not in mail["html"]
    assert MARKER not in mail["text"]
    # The report did carry it: absent from the mail by design, not by accident.
    assert MARKER in _row(aid).raw_output


def test_a_mail_that_raises_leaves_the_status_alone(app, make_user):
    aid = _queued(make_user())
    with patch(READY, side_effect=RuntimeError("resend down")):
        _run(app, aid, _streaming_client())      # must not raise
    assert _row(aid).status == "success"


def test_the_mail_leaves_after_the_connection_is_released(app, make_user):
    """No pooled connection held across the HTTP call to Resend — the same
    discipline as the stream in _run_analysis."""
    aid = _queued(make_user())
    seen = []
    with patch(READY, side_effect=lambda *a, **k: seen.append(db.session().in_transaction())):
        _run(app, aid, _streaming_client())
    assert seen == [False]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && ./venv/bin/python -m pytest -q -p no:cacheprovider tests/test_analysis_outcome_mail.py`
Expected: `8 failed, 3 passed` — e.g. `AssertionError: Expected 'send_analysis_ready' to be called once. Called 0 times.` The three that pass already are the two "sends nothing" tests and `test_a_mail_that_raises_leaves_the_status_alone`; that is expected.

- [ ] **Step 3: Implement `_notify_outcome` and call it at each final exit**

In `backend/app/services/anthropic_service.py`:

(a) Replace the import block

```python
import anthropic
from json_repair import repair_json

from ..extensions import db
from ..models.analysis import Analysis
from ..models.prompt_version import PromptVersion
from . import section_registry as registry
from . import tiers
```

with

```python
import anthropic
from flask import current_app
from json_repair import repair_json

from ..extensions import db
from ..models.analysis import Analysis
from ..models.prompt_version import PromptVersion
from . import email_service
from . import section_registry as registry
from . import tiers
```

(b) In `_run_analysis`, the « Aucun prompt actif » exit — replace

```python
        if not prompt:
            analysis.status = "error"
            analysis.raw_output = f"Aucun prompt actif pour le chemin {path}."
            db.session.commit()
            return
```

with

```python
        if not prompt:
            analysis.status = "error"
            analysis.raw_output = f"Aucun prompt actif pour le chemin {path}."
            db.session.commit()
            _notify_outcome(analysis_id)
            return
```

(c) The stream-failure exit — replace

```python
            analysis.raw_output = str(error_exc)[:2000]
            db.session.commit()
            return
```

with

```python
            analysis.raw_output = str(error_exc)[:2000]
            db.session.commit()
            _notify_outcome(analysis_id)
            return
```

(d) The success exit, at the end of `_run_analysis` — replace

```python
        analysis.completed_at = datetime.utcnow()
        db.session.commit()
```

with

```python
        analysis.completed_at = datetime.utcnow()
        db.session.commit()
        _notify_outcome(analysis_id)
```

(e) In the `_run_analysis` docstring, replace the first line

```python
    """Run a single analysis to completion. Writes status + output to DB.
```

with

```python
    """Run a single analysis to completion. Writes status + output to DB, then
    mails the owner (_notify_outcome) after each final commit.
```

(f) Insert this function between the end of `_run_analysis` and `def start_analysis`:

```python
def _notify_outcome(analysis_id: str) -> None:
    """Mail the owner how the run ended. Called after each final commit.

    Every finished run is mailed, watched or not (transactional mails spec,
    decision 2), and the mail carries no report text (decision 7). Reads what
    it needs, then releases the connection before the HTTP call to Resend —
    the discipline the stream above keeps. Never raises and never writes: the
    status is already committed, and a mail failure must not reach it.
    """
    try:
        analysis = db.session.get(Analysis, analysis_id)
        user = analysis.user if analysis is not None else None
        # No mail to an address nobody proved (decision 8); an ownerless row
        # predates accounts.
        if user is None or user.email_verified_at is None:
            return
        to, prenom = user.email, email_service.prenom_of(user)
        status = analysis.status
        # unlock_service writes unlock_method before it requeues the row, so
        # it marks the second run — bought or by code alike.
        unlocked = analysis.unlock_method is not None
        db.session.remove()

        if status == "success":
            email_service.send_analysis_ready(to, prenom, unlocked=unlocked)
        elif status in ("error", "timeout"):
            email_service.send_analysis_failed(
                to, prenom, unlocked=unlocked, analysis_id=analysis_id
            )
    except Exception:
        current_app.logger.exception("Could not mail the outcome of analysis %s.", analysis_id)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && ./venv/bin/python -m pytest -q -p no:cacheprovider tests/test_analysis_outcome_mail.py tests/test_stream_progress.py tests/test_unlock.py tests/test_stale_reaper.py tests/test_anthropic_service.py`
Expected: all pass (11 in `test_analysis_outcome_mail.py`).

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/anthropic_service.py backend/tests/test_analysis_outcome_mail.py
git commit -m "feat(analyses): mail the owner when a run ends

Ready or failed, first run or the one an unlock starts, after the final
commit and with the connection released first. Verified owners only; no
report text in the mail; a mail failure never touches the status.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Tell the conseiller on revoke, the owner after a reset

**Files:**
- Modify: `backend/app/routes/admin.py` — `revoke_counselor_application`
- Modify: `backend/app/routes/auth.py` — services import; `reset_password`
- Test: `backend/tests/test_counselor_review.py` (append; add `import pytest`), `backend/tests/test_auth_link_routes.py` (append)

**Interfaces:**
- Consumes: Task 2's `email_service.send_counselor_revoked(profile)` and `email_service.send_password_changed(user)`.
- Produces: no new names. Task 5 edits `reset_password` again; it expects the exact text this task leaves (Step 3c).

- [ ] **Step 1: Write the failing tests**

At the top of `backend/tests/test_counselor_review.py`, add `import pytest` under `from unittest.mock import patch`, so the imports begin:

```python
from datetime import datetime
from unittest.mock import patch

import pytest
from flask_jwt_extended import create_access_token, create_refresh_token
```

Append to `backend/tests/test_counselor_review.py`:

```python
def _active_conseiller():
    user, profile = _demande(status="approved")
    user.role = "counselor"
    db.session.commit()
    return user, profile


def test_revoking_mails_the_conseiller_the_reason(client, admin_headers, app):
    _user, profile = _active_conseiller()
    with patch("app.services.email_service.send") as mock_send:
        r = client.post(
            f"/api/admin/counselor-applications/{profile.id}/revoke",
            json={"reason": "Fin de convention."}, headers=admin_headers,
        )
    assert r.status_code == 200
    mock_send.assert_called_once()
    to, subject, _html, text = mock_send.call_args[0]
    assert to == "conseiller@test.com"
    assert subject == "Votre accès conseiller"
    assert "Fin de convention." in text


@pytest.mark.parametrize("status, body", [
    ("pending", {"reason": "Fin de convention."}),   # 409: not an active conseiller
    ("approved", {}),                                # 400: no reason given
])
def test_a_refused_revocation_mails_nobody(client, admin_headers, app, status, body):
    _user, profile = _demande(status=status)
    with patch("app.services.email_service.send") as mock_send:
        r = client.post(
            f"/api/admin/counselor-applications/{profile.id}/revoke",
            json=body, headers=admin_headers,
        )
    assert r.status_code in (400, 409)
    mock_send.assert_not_called()


def test_a_mail_failure_does_not_undo_the_revocation(client, admin_headers, app):
    # Review Focus 4: the decision has committed before the mail is tried.
    user, profile = _active_conseiller()
    app.config["RESEND_API_KEY"] = "re_test"
    with patch("app.services.email_service.resend.Emails.send",
               side_effect=RuntimeError("resend down")):
        r = client.post(
            f"/api/admin/counselor-applications/{profile.id}/revoke",
            json={"reason": "Fin de convention."}, headers=admin_headers,
        )
    assert r.status_code == 200
    db.session.refresh(profile)
    db.session.refresh(user)
    assert profile.status == "revoked"
    assert user.role == "candidate"
```

Append to `backend/tests/test_auth_link_routes.py`:

```python
# ── the password-changed notice ──────────────────────────────────────────────

def test_a_reset_tells_the_address_the_password_changed(client, app, make_user):
    app.config["RESEND_API_KEY"] = "re_test"
    user = make_user(email="reset@test.fr")
    with patch(SEND, return_value={"id": "1"}) as mock_send:
        assert _reset(client, auth_links.make_reset_token(user)).status_code == 200
    mock_send.assert_called_once()
    mail = mock_send.call_args[0][0]
    assert mail["to"] == ["reset@test.fr"]
    assert mail["subject"] == "Votre mot de passe a été modifié"
    # A notice, not an account mail: the one-a-minute clock is not touched.
    assert _fresh(user).auth_mail_sent_at is None


def test_a_refused_reset_sends_no_notice(client, app, make_user):
    app.config["RESEND_API_KEY"] = "re_test"
    token = auth_links.make_reset_token(make_user())
    with patch(SEND, return_value={"id": "1"}) as mock_send:
        assert _reset(client, token, "court").status_code == 400      # password refused
        assert _reset(client, "pas-un-lien").status_code == 400       # dead link
    mock_send.assert_not_called()


def test_a_reset_survives_a_mail_outage(client, app, make_user):
    # Review Focus 4: the password changes and the session opens anyway.
    app.config["RESEND_API_KEY"] = "re_test"
    user = make_user(email="reset@test.fr")
    with patch(SEND, side_effect=RuntimeError("resend down")):
        res = _reset(client, auth_links.make_reset_token(user))
    assert res.status_code == 200
    assert "access_token_cookie" in _cookies(res)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && ./venv/bin/python -m pytest -q -p no:cacheprovider tests/test_counselor_review.py tests/test_auth_link_routes.py`
Expected: `2 failed` — `test_revoking_mails_the_conseiller_the_reason` (`Expected 'send' to have been called once. Called 0 times.`) and `test_a_reset_tells_the_address_the_password_changed` (same). The refusal and outage tests pass already; that is expected.

- [ ] **Step 3: Send the two mails**

(a) In `backend/app/routes/admin.py`, `revoke_counselor_application` — replace

```python
    _decide(profile, "revoked", reason, get_jwt_identity())
    db.session.commit()
    return jsonify({"application": profile.to_dict(with_user=True)}), 200
```

with

```python
    _decide(profile, "revoked", reason, get_jwt_identity())
    db.session.commit()

    email_service.send_counselor_revoked(profile)
    return jsonify({"application": profile.to_dict(with_user=True)}), 200
```

(b) In `backend/app/routes/auth.py`, replace the import line

```python
from ..services import auth_mail
```

with

```python
from ..services import auth_mail, email_service
```

(c) In `reset_password`, replace

```python
    if user.email_verified_at is None:
        user.email_verified_at = datetime.utcnow()
    db.session.commit()

    response = jsonify({"user": user.to_dict()})
```

with

```python
    if user.email_verified_at is None:
        user.email_verified_at = datetime.utcnow()
    db.session.commit()

    # After the commit, like every mail. It reaches the address's owner even
    # when someone else held the link; not paced by auth_mail_sent_at, since
    # the link that made this reset possible already was.
    email_service.send_password_changed(user)

    response = jsonify({"user": user.to_dict()})
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && ./venv/bin/python -m pytest -q -p no:cacheprovider tests/test_counselor_review.py tests/test_auth_link_routes.py tests/test_admin.py tests/test_auth_gate.py`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/routes/admin.py backend/app/routes/auth.py backend/tests/test_counselor_review.py backend/tests/test_auth_link_routes.py
git commit -m "feat(mail): tell the conseiller on revoke, the owner after a reset

Revoke mails like approve and reject do, with the reason the conseiller
already sees on their page. A reset tells the address its password moved,
unpaced, since the reset link itself was.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Tell the admins when a demande joins the queue

**Files:**
- Create: `backend/app/services/demande_mail.py`
- Modify: `backend/app/routes/counselor_space.py` — services import; end of `apply()`
- Modify: `backend/app/routes/auth.py` — services import; `verify_email`; `reset_password`
- Create: `backend/tests/test_demande_mail.py`

**Interfaces:**
- Consumes: Task 2's `email_service.send_new_demande(admin)` (an admin `User`), called through the module. Task 4's `reset_password` text (Step 3d below shows it in full).
- Produces: `app.services.demande_mail.notify_if_visible(user) -> None`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_demande_mail.py`:

```python
"""A new conseiller demande mails the admins once, when its address is proven
(transactional mails spec, 2026-10-02)."""
import logging
from unittest.mock import patch

import pytest
from flask_jwt_extended import create_access_token

from app.extensions import db
from app.models.counselor_profile import CounselorProfile
from app.models.user import User
from app.services import demande_mail
from app.utils import auth_links

NEW_DEMANDE = "app.services.email_service.send_new_demande"
SEND = "app.services.email_service.resend.Emails.send"

# The demande form, without the account half (a signed-in applicant has one).
DEMANDE = {
    "structure": "Cap Emploi 31",
    "type_structure": "cap_emploi",
    "siret": "12345678901234",
    "adresse_rue": "12 rue des Lois",
    "adresse_code_postal": "31000",
    "adresse_ville": "Toulouse",
    "domaines": ["insertion_emploi"],
    "nom_complet": "Claire Martin",
    "fonction": "Conseillère en insertion",
    "telephone": "0561000000",
    "consent": True,
    "consent_donnees": True,
}
ACCOUNT = {"email": "claire@capemploi.fr", "password": "motdepasse1"}


def _admin(make_user, email="admin@neoori.tech", verified=True):
    return make_user(email=email, role="admin", verified=verified)


def _pending(make_user, email="claire@capemploi.fr"):
    """A verified account holding a pending demande."""
    user = make_user(email=email)
    db.session.add(CounselorProfile(user_id=user.id, structure="Cap Emploi 31",
                                    fonction="Conseillère", telephone="0561000000"))
    db.session.commit()
    return user


def _signed_in(user) -> dict:
    token = create_access_token(identity=str(user.id), additional_claims={"role": user.role})
    return {"Authorization": f"Bearer {token}"}


def _told(mock_new_demande) -> list[str]:
    return [c.args[0].email for c in mock_new_demande.call_args_list]


def _apply_without_account(client) -> User:
    assert client.post("/api/counselor/apply", json={**DEMANDE, **ACCOUNT}).status_code == 201
    return User.query.filter_by(email=ACCOUNT["email"]).one()


def _verify(client, user):
    return client.post("/api/auth/verify-email", json={
        "token": auth_links.make_verify_token(user), "password": ACCOUNT["password"],
    })


def _reset(client, user):
    return client.post("/api/auth/reset-password", json={
        "token": auth_links.make_reset_token(user), "password": "nouveau-mdp1",
    })


# ── the three doors into the queue ───────────────────────────────────────────

def test_a_signed_in_applicant_reaches_the_admins_at_once(client, make_user):
    admin = _admin(make_user)
    applicant = make_user(email="claire@capemploi.fr")       # verified
    with patch(NEW_DEMANDE) as told:
        r = client.post("/api/counselor/apply", json=DEMANDE, headers=_signed_in(applicant))
    assert r.status_code == 201
    assert _told(told) == [admin.email]


def test_a_new_account_demande_waits_for_its_address(client, make_user):
    admin = _admin(make_user)
    with patch(NEW_DEMANDE) as told:
        applicant = _apply_without_account(client)
    told.assert_not_called()

    with patch(NEW_DEMANDE) as told:
        assert _verify(client, applicant).status_code == 200
    assert _told(told) == [admin.email]

    # A second use of the link is a login: nobody is told twice.
    with patch(NEW_DEMANDE) as told:
        assert _verify(client, applicant).status_code == 200
    told.assert_not_called()


def test_a_reset_that_proves_the_address_tells_the_admins(client, make_user):
    admin = _admin(make_user)
    applicant = _apply_without_account(client)
    with patch(NEW_DEMANDE) as told:
        assert _reset(client, applicant).status_code == 200
    assert _told(told) == [admin.email]


def test_a_reset_of_a_proven_address_tells_nobody_again(client, make_user):
    _admin(make_user)
    applicant = _pending(make_user)                            # already verified
    with patch(NEW_DEMANDE) as told:
        assert _reset(client, applicant).status_code == 200
    told.assert_not_called()


def test_marking_an_address_verified_by_hand_tells_nobody(client, admin_headers, make_user):
    """« Marquer comme vérifié » is the fourth way an address gets proven, and
    deliberately not a door: the admin who clicked is already in the queue."""
    _admin(make_user)
    applicant = _apply_without_account(client)
    with patch(NEW_DEMANDE) as told:
        r = client.post(f"/api/admin/users/{applicant.id}/verify-email", headers=admin_headers)
    assert r.status_code == 200
    told.assert_not_called()


# ── what counts as news, and who hears it ────────────────────────────────────

@pytest.mark.parametrize("status", ["approved", "rejected", "revoked"])
def test_only_a_pending_demande_is_news(app, make_user, status):
    _admin(make_user)
    user = make_user(email="claire@capemploi.fr")
    db.session.add(CounselorProfile(user_id=user.id, structure="X", fonction="Y",
                                    telephone="0102030405", status=status))
    db.session.commit()
    with patch(NEW_DEMANDE) as told:
        demande_mail.notify_if_visible(user)
    told.assert_not_called()


def test_a_candidate_without_a_demande_is_not_news(app, make_user):
    _admin(make_user)
    with patch(NEW_DEMANDE) as told:
        demande_mail.notify_if_visible(make_user(email="marie@test.fr"))
    told.assert_not_called()


def test_every_verified_admin_is_told_and_no_one_else(app, make_user):
    _admin(make_user, "a1@neoori.tech")
    _admin(make_user, "a2@neoori.tech")
    _admin(make_user, "a3@neoori.tech", verified=False)
    make_user(email="candidat@test.fr")
    applicant = _pending(make_user)
    with patch(NEW_DEMANDE) as told:
        demande_mail.notify_if_visible(applicant)
    assert sorted(_told(told)) == ["a1@neoori.tech", "a2@neoori.tech"]


def test_one_failed_send_does_not_cost_the_other_admin_their_mail(app, make_user):
    app.config["RESEND_API_KEY"] = "re_test"
    _admin(make_user, "a1@neoori.tech")
    _admin(make_user, "a2@neoori.tech")
    applicant = _pending(make_user)
    with patch(SEND, side_effect=[RuntimeError("bounce"), {"id": "2"}]) as mock_send:
        demande_mail.notify_if_visible(applicant)
    assert mock_send.call_count == 2


def test_no_verified_admin_is_a_warning_not_a_crash(app, make_user, caplog):
    applicant = _pending(make_user)
    with patch(NEW_DEMANDE) as told, caplog.at_level(logging.WARNING):
        demande_mail.notify_if_visible(applicant)
    told.assert_not_called()
    assert "no verified admin" in caplog.text


def test_the_admin_mail_carries_nothing_of_the_applicant(client, app, make_user):
    app.config["RESEND_API_KEY"] = "re_test"
    admin = _admin(make_user)
    applicant = make_user(email="claire@capemploi.fr")
    with patch(SEND, return_value={"id": "1"}) as mock_send:
        client.post("/api/counselor/apply", json=DEMANDE, headers=_signed_in(applicant))
    mail = mock_send.call_args[0][0]
    assert mail["to"] == [admin.email]
    for detail in ("Claire Martin", "Cap Emploi 31", "0561000000", "12345678901234",
                   "Toulouse", "claire@capemploi.fr"):
        assert detail not in mail["html"]
        assert detail not in mail["text"]


def test_a_failed_admin_lookup_does_not_block_the_verification(client, make_user):
    # Review Focus 3: the person proved their address. A 500 here would keep
    # them out over a mail they never asked for.
    _admin(make_user)
    applicant = _apply_without_account(client)
    with patch("app.services.demande_mail.CounselorProfile") as broken:
        broken.query.filter_by.side_effect = RuntimeError("Lost connection")
        r = _verify(client, applicant)
    assert r.status_code == 200
    assert "access_token_cookie" in " ".join(r.headers.getlist("Set-Cookie"))
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && ./venv/bin/python -m pytest -q -p no:cacheprovider tests/test_demande_mail.py`
Expected: collection ERROR — `ImportError: cannot import name 'demande_mail' from 'app.services'`.

- [ ] **Step 3: Implement the module and its three call sites**

(a) Create `backend/app/services/demande_mail.py`:

```python
"""The admin's half of a conseiller demande: a mail when one joins the queue.

A demande becomes admin work when its address is proven —
admin.list_counselor_applications filters on email_verified_at (email
verification spec, decision 16). That happens at one of three doors, and each
calls notify_if_visible() after its own commit:

  counselor_space.apply()   a signed-in, hence verified, applicant
  auth.verify_email()       the email_verified_at None -> set write
  auth.reset_password()     the same write, made by a reset link

email_verified_at goes None -> set once per account, and an account holds one
demande, so each demande mails the admins once (transactional mails spec,
2026-10-02). Admin « Marquer comme vérifié » does not call this: the admin who
clicked is already looking at the queue.
"""
from flask import current_app

from ..models.counselor_profile import CounselorProfile
from ..models.user import User
from . import email_service


def notify_if_visible(user) -> None:
    """Mail every verified admin that `user`'s demande is waiting. Fail-soft:
    the caller has committed, and an admin lookup or a provider failure must
    not turn a verification into a 500."""
    try:
        if user.email_verified_at is None:
            return
        if CounselorProfile.query.filter_by(user_id=user.id, status="pending").first() is None:
            return
        # Looked up at send time, so adding or removing an admin in /admin
        # moves the mail with it — no address to keep in the VPS env.
        admins = User.query.filter(
            User.role == "admin", User.email_verified_at.isnot(None)
        ).all()
    except Exception:
        current_app.logger.exception("Could not look up the demande or the admins to tell.")
        return
    if not admins:
        current_app.logger.warning("A conseiller demande is waiting, and no verified admin to tell.")
        return
    # One send per address. send_new_demande is fail-soft, so one bad address
    # does not cost the others their mail.
    for admin in admins:
        email_service.send_new_demande(admin)
```

(b) In `backend/app/routes/counselor_space.py`, replace the import line

```python
from ..services import auth_mail, code_service
```

with

```python
from ..services import auth_mail, code_service, demande_mail
```

and at the end of `apply()`, replace

```python
        body["mail_sent"] = auth_mail.verification_if_due(user, "/conseiller")
    return jsonify(body), 201
```

with

```python
        body["mail_sent"] = auth_mail.verification_if_due(user, "/conseiller")
    else:
        # Signed in means a proven address (no session before one), so this
        # demande is in the admin queue from the commit above.
        demande_mail.notify_if_visible(user)
    return jsonify(body), 201
```

(c) In `backend/app/routes/auth.py`, replace the import line (as Task 4 left it)

```python
from ..services import auth_mail, email_service
```

with

```python
from ..services import auth_mail, demande_mail, email_service
```

and in `verify_email`, replace

```python
    if user.email_verified_at is None:
        user.email_verified_at = datetime.utcnow()
        db.session.commit()

    response = jsonify({"user": user.to_dict(), "next": _landing(user, payload)})
```

with

```python
    if user.email_verified_at is None:
        user.email_verified_at = datetime.utcnow()
        db.session.commit()
        # This address's first proof: a demande waiting on it joins the admin
        # queue now. A second use of the link is a login and skips this.
        demande_mail.notify_if_visible(user)

    response = jsonify({"user": user.to_dict(), "next": _landing(user, payload)})
```

(d) In `reset_password`, replace (the text Task 4 left)

```python
    # Opening the link proved the inbox, exactly as the verification link
    # does (spec decision 12).
    if user.email_verified_at is None:
        user.email_verified_at = datetime.utcnow()
    db.session.commit()

    # After the commit, like every mail. It reaches the address's owner even
    # when someone else held the link; not paced by auth_mail_sent_at, since
    # the link that made this reset possible already was.
    email_service.send_password_changed(user)
```

with

```python
    # Opening the link proved the inbox, exactly as the verification link
    # does (spec decision 12).
    newly_verified = user.email_verified_at is None
    if newly_verified:
        user.email_verified_at = datetime.utcnow()
    db.session.commit()

    # After the commit, like every mail. It reaches the address's owner even
    # when someone else held the link; not paced by auth_mail_sent_at, since
    # the link that made this reset possible already was.
    email_service.send_password_changed(user)
    if newly_verified:
        # The same first proof verify_email() reacts to, by the other door.
        demande_mail.notify_if_visible(user)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && ./venv/bin/python -m pytest -q -p no:cacheprovider tests/test_demande_mail.py tests/test_counselor_apply.py tests/test_auth_link_routes.py tests/test_counselor_review.py tests/test_admin_email_verification.py`
Expected: all pass (14 in `test_demande_mail.py`).

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/demande_mail.py backend/app/routes/counselor_space.py backend/app/routes/auth.py backend/tests/test_demande_mail.py
git commit -m "feat(counselor): tell the admins when a demande joins the queue

Every verified admin, looked up at send time, once per demande: when a
signed-in applicant applies, or when an applicant's address is first
proven, by its link or by a reset. Nothing about the applicant in the mail.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: The waiting page says the mail will come

**Files:**
- Modify: `frontend/src/app/analyse/en-cours/[id]/page.tsx`

**Interfaces:**
- Consumes: nothing from earlier tasks at build time. At run time it relies on Task 3: a run that outlives the page still mails its owner.
- Produces: no exports. A local `stalled` state — named after the voyage page's identical give-up (`frontend/src/app/voyage/page.tsx`, `stalled` / `setStalled`).

There is no frontend test runner in this repo (`package.json` has no test script). This task is checked by typecheck and lint here, and in the browser in Task 7.

- [ ] **Step 1: Record the lint baseline**

Run: `cd frontend && npx eslint "src/app/analyse/en-cours/[id]/page.tsx"`
Expected: `✖ 1 problem (1 error, 0 warnings)` — `Cannot call impure function during render` on `const startRef  = useRef(Date.now())`. It predates this branch; leave it.

- [ ] **Step 2: Edit the page**

In `frontend/src/app/analyse/en-cours/[id]/page.tsx`:

(a) Replace

```tsx
const POLL_MAX_MS      = 10 * 60 * 1000   // give up after 10 min total
```

with

```tsx
const POLL_MAX_MS      = 10 * 60 * 1000   // stop watching after 10 min; the mail takes over
```

(b) Replace

```tsx
  const [error,      setError]       = useState<string | null>(null)
```

with

```tsx
  const [error,      setError]       = useState<string | null>(null)
  // This page stopped watching, not the server: a run past POLL_MAX_MS may
  // still finish, and its mail says so. Not an error, so not « n'a pas abouti ».
  const [stalled,    setStalled]     = useState(false)
```

(c) Replace

```tsx
      if (Date.now() - startRef.current > POLL_MAX_MS) {
        setError("L'analyse a expiré. Veuillez réessayer.")
        return
      }
```

with

```tsx
      if (Date.now() - startRef.current > POLL_MAX_MS) {
        setStalled(true)
        return
      }
```

Leave the other `setError("L'analyse a expiré. Veuillez réessayer.")`, under `if (status === "timeout")`, as it is: that one is the server's verdict.

(d) Replace

```tsx
            <InfinityMark animate={!error} className="h-[1.2em]" />
            {error
              ? "Analyse interrompue"
              : `Analyse en cours${hint ? ` · ${hint}` : ""}`}
          </p>
          <h1 className="font-display text-3xl font-bold tracking-tight text-navy">
            {error ? "L’analyse n’a pas abouti" : "Analyse en cours"}
          </h1>
          <p className="mx-auto mt-2 max-w-sm text-sm text-muted-foreground">
            {error
              ? "Vous pouvez relancer une analyse, vos informations sont conservées."
              : "Nous lisons votre profil et préparons votre rapport."}
          </p>
```

with

```tsx
            <InfinityMark animate={!error && !stalled} className="h-[1.2em]" />
            {error
              ? "Analyse interrompue"
              : `Analyse en cours${hint && !stalled ? ` · ${hint}` : ""}`}
          </p>
          <h1 className="font-display text-3xl font-bold tracking-tight text-navy">
            {error
              ? "L’analyse n’a pas abouti"
              : stalled
                ? "C’est plus long que prévu"
                : "Analyse en cours"}
          </h1>
          <p className="mx-auto mt-2 max-w-sm text-sm text-muted-foreground">
            {error
              ? "Vous pouvez relancer une analyse, vos informations sont conservées."
              : stalled
                ? "Vous recevrez un email dès qu’elle sera prête."
                : "Nous lisons votre profil et préparons votre rapport."}
          </p>
```

(e) Replace

```tsx
        ) : (
          <div className="rounded-2xl border border-border bg-card p-6 shadow-card sm:p-8">
            <ol className="mb-7 space-y-0">
```

with

```tsx
        ) : stalled ? (
          <div className="rounded-2xl border border-border bg-card p-6 text-center shadow-card sm:p-8">
            {/* Not « Nouvelle analyse »: the first run may still be going, and
                a second would cost a second generation. */}
            <Button variant="navy" size="lg" onClick={() => router.push("/espace")}>
              <ArrowLeft className="size-4" />
              Retour à mon espace
            </Button>
          </div>
        ) : (
          <div className="rounded-2xl border border-border bg-card p-6 shadow-card sm:p-8">
            <ol className="mb-7 space-y-0">
```

(f) Replace

```tsx
                Laissez cet onglet ouvert, le rapport s’affiche automatiquement.
```

with

```tsx
                Le rapport s’affiche ici automatiquement. Vous recevrez un email quand il sera prêt — vous pouvez fermer cette page.
```

- [ ] **Step 3: Typecheck and lint**

Run: `cd frontend && npx tsc --noEmit -p .`
Expected: no output (exit 0).

Run: `cd frontend && npx eslint "src/app/analyse/en-cours/[id]/page.tsx"`
Expected: still exactly `✖ 1 problem (1 error, 0 warnings)` — the same `useRef(Date.now())` error. Nothing new.

Run: `cd frontend && grep -n "Laissez cet onglet\|setError(\"L'analyse a expiré" "src/app/analyse/en-cours/[id]/page.tsx"`
Expected: exactly one line — the `setError` under `status === "timeout"`.

- [ ] **Step 4: Commit**

```bash
git add "frontend/src/app/analyse/en-cours/[id]/page.tsx"
git commit -m "feat(frontend): the waiting page says the mail will come

The running card no longer asks to keep the tab open: the report appears
here, and a mail follows. At the 10-minute give-up the page stops
watching without calling it an error, and sends the person to the espace
rather than to a second, paid-for generation.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Docs, the whole suite, and the mails end to end

**Files:**
- Modify: `CLAUDE.md` — new `## Mails transactionnels` section between the Email verification section and `## Out of scope`

**Interfaces:**
- Consumes: everything above.
- Produces: the report to the developer.

- [ ] **Step 1: Document the mails**

In `CLAUDE.md`, replace

```markdown
Spec: `docs/superpowers/specs/2026-09-29-email-verification-design.md`

## Out of scope
```

with

```markdown
Spec: `docs/superpowers/specs/2026-09-29-email-verification-design.md`

## Mails transactionnels

Every mail is built in `services/email_service.py`, leaves after the commit
that decided it, and is fail-soft: a Resend failure logs and returns False —
never a 500, never a rolled-back write. No mail carries content: no report
text, no voyage text, no applicant data. Each one says something happened and
links to where it can be read behind a login. HTML and plain text come from
one paragraph list (`_mail`), so a wording edit reaches both.

| Mail | To | Sent by |
|---|---|---|
| Confirmez votre adresse | the account | signup, conseiller demande, resend — `services/auth_mail.py` |
| Réinitialiser votre mot de passe | the account | « mot de passe oublié » — `services/auth_mail.py` |
| Votre mot de passe a été modifié | the account | `auth.reset_password`, after its commit |
| Votre analyse est prête / n'a pas abouti | the analysis owner, verified only | `anthropic_service._notify_outcome`, at every final status |
| Nouvelle demande de compte conseiller | every verified admin | `services/demande_mail.notify_if_visible` |
| Compte activé / demande non retenue / accès retiré | the conseiller | `admin` approve / reject / revoke |

- **The analysis mail goes out on every finished run, watched or not.** That
  is what lets the waiting page say « vous pouvez fermer cette page », and why
  its 10-minute give-up reads « C'est plus long que prévu », not an error.
- **The run an unlock starts (`unlock_method` set) has its own wording.** When
  it fails, the code is still a dead end — a second unlock is a 409 — so the
  mail asks the candidate to reply, with the analysis id. Relaunching it is
  manual.
- **The admin mail fires when a demande enters the queue**: a signed-in
  applicant applies, or an applicant's address is proven for the first time,
  by its verification link or by a reset link. Admin « Marquer comme vérifié »
  does not send it.
- Resend's free plan is 100 mails a day, shared by every mail above.

Spec: `docs/superpowers/specs/2026-10-02-transactional-mails-design.md`

## Out of scope
```

- [ ] **Step 2: Commit the docs**

```bash
git add CLAUDE.md
git commit -m "docs: the transactional mails, in one place

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

- [ ] **Step 3: Run the whole backend suite**

Run: `cd backend && ./venv/bin/python -m pytest -q -p no:cacheprovider`
Expected: `1197 passed` — the 1151 baseline plus 46 new (6 + 8 in `test_transactional_mails.py`, 11 in `test_analysis_outcome_mail.py`, 4 + 3 in the review and link-route suites, 14 in `test_demande_mail.py`). Any failure stops here.

- [ ] **Step 4: Print every new mail, for the report**

Throwaway, not committed:

```bash
cd backend && ./venv/bin/python - <<'EOF' 2>/dev/null
from unittest.mock import patch
from app import create_app
from app.extensions import db
from app.models.counselor_profile import CounselorProfile
from app.models.user import User
from app.services import email_service as es

app = create_app("testing")
with app.app_context():
    db.create_all()
    app.config["RESEND_API_KEY"] = "re_print"
    u = User(email="marie@test.fr", password_hash="x")
    db.session.add(u)
    db.session.commit()
    p = CounselorProfile(user_id=u.id, structure="S", fonction="F", telephone="0",
                         status="revoked", decision_reason="Fin de convention.")
    db.session.add(p)
    db.session.commit()
    with patch("app.services.email_service.resend.Emails.send") as s:
        es.send_analysis_ready(u.email, "Marie", unlocked=False)
        es.send_analysis_ready(u.email, "Marie", unlocked=True)
        es.send_analysis_failed(u.email, "Marie", unlocked=False, analysis_id="3f2a9c1e")
        es.send_analysis_failed(u.email, "Marie", unlocked=True, analysis_id="3f2a9c1e")
        es.send_new_demande(u)
        es.send_counselor_revoked(p)
        es.send_password_changed(u)
    for call in s.call_args_list:
        m = call[0][0]
        print("=" * 64)
        print("Objet :", m["subject"])
        print(m["text"])
EOF
```

Expected: seven mails, each subject and body word for word as in the spec's « Mails » section. Keep the output for the report.

- [ ] **Step 5: Bring up the dev stack**

```bash
cd /Users/imran/Downloads/design_handoff_cv_analyzer
docker compose up -d
until curl -sf http://localhost:8080/api/health >/dev/null; do sleep 2; done
grep -c '^RESEND_API_KEY=.\+' backend/.env
```

Expected: the stack answers on :8080, and the count is `0`. With no key, no mail leaves the laptop: the verification and reset links are printed as `DEV — no RESEND_API_KEY, link for <address>: <link>`, and every other mail as `RESEND_API_KEY missing — mail to <address> not sent.` In the steps below, "log" means `docker compose logs backend --since 5m`.

If a later `register` or `apply` answers 409, the address exists from an earlier run: bump the number (`e2e-mails-1` → `e2e-mails-11`) everywhere in that step.

- [ ] **Step 6: E2E — the analysis mail and the waiting page**

This makes **one real generation** on the developer's Anthropic key (paid tier, since `FORCE_ANALYSIS_TIER` defaults to `paid`: about 2 minutes, roughly $0.10–0.15).

1. Sign up:
   ```bash
   curl -s -X POST http://localhost:8080/api/auth/register -H 'Content-Type: application/json' \
     -d '{"email":"e2e-mails-1@test.fr","password":"motdepasse-e2e1","prenom":"Marie","tranche_age":"25_34","consent":true}'
   docker compose logs backend --since 2m | grep "link for e2e-mails-1@test.fr"
   ```
   Open the printed `/verifier-email?token=…` link in the browser and enter `motdepasse-e2e1`. Expected: signed in.

2. From that tab, start an analysis with the page's own session (DevTools console or the browser tool's JavaScript):
   ```js
   const r = await fetch('/api/analyses/', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({inputs: {_path: '1', cv_text: 'Conseillère clientèle depuis 2015 dans une agence bancaire de Toulouse : accueil, ouverture de comptes, suivi d’un portefeuille de 400 clients particuliers, formation des nouveaux arrivants, animation de réunions d’équipe hebdomadaires, reporting mensuel des objectifs commerciaux.', cible_visee: 'Chargée de recrutement dans un cabinet RH ou une entreprise de taille moyenne, en région toulousaine.'}})}); (await r.json()).analysis.id
   ```
   Open `http://localhost:8080/analyse/en-cours/<that id>`. Expected: the running card ends with « Le rapport s’affiche ici automatiquement. Vous recevrez un email quand il sera prêt — vous pouvez fermer cette page. » — and « Laissez cet onglet ouvert » appears nowhere.

3. Force the 10-minute give-up without waiting, in the same tab:
   ```js
   Date.now = ((now) => () => now() + 11 * 60 * 1000)(Date.now.bind(Date))
   ```
   Expected within about 2 s: eyebrow « Analyse en cours » with no duration hint; heading « C’est plus long que prévu »; text « Vous recevrez un email dès qu’elle sera prête. »; a single button, « Retour à mon espace ». Screenshot it. Click the button. Expected: `/espace`.
   Then open `http://localhost:8080/analyse/en-cours/<id>` again — a fresh load, without the override (Review Focus 5). Expected: polling resumes, and once the run has finished the page moves to `/analyse/<id>/rapport`.

4. Expected in the log, after the run finished: exactly one `RESEND_API_KEY missing — mail to e2e-mails-1@test.fr not sent.`, and no `Could not mail the outcome` line.

- [ ] **Step 7: E2E — the password-changed notice**

```bash
curl -s -X POST http://localhost:8080/api/auth/forgot-password -H 'Content-Type: application/json' -d '{"email":"e2e-mails-1@test.fr"}'
docker compose logs backend --since 1m | grep "link for e2e-mails-1@test.fr"
```

The signup mail stamped the one-a-minute clock: if no link prints, wait a minute and repeat. Take the token from the `/reinitialiser-mot-de-passe?token=…` link, then:

```bash
curl -s -X POST http://localhost:8080/api/auth/reset-password -H 'Content-Type: application/json' \
  -d '{"token":"<TOKEN>","password":"nouveau-mdp-e2e1"}' -o /dev/null -w '%{http_code}\n'
docker compose logs backend --since 1m | grep "mail to"
```

Expected: `200`, then exactly one `mail to e2e-mails-1@test.fr not sent.` line — the notice. No admin line: this address was already verified.

- [ ] **Step 8: E2E — the demande reaches the admins once**

Make `e2e-mails-1` an admin, so it both receives the demande mail and can revoke in Step 9, and list who should be told:

```bash
docker compose exec -T db mysql -uneoori -pneoori_dev neoori -e \
  "UPDATE users SET role='admin' WHERE email='e2e-mails-1@test.fr'; SELECT email FROM users WHERE role='admin' AND email_verified_at IS NOT NULL;"
```

File a demande without an account:

```bash
curl -s -X POST http://localhost:8080/api/counselor/apply -H 'Content-Type: application/json' \
  -d '{"email":"e2e-mails-2@test.fr","password":"motdepasse-e2e2","structure":"Cap Emploi 31","type_structure":"cap_emploi","siret":"12345678901234","adresse_rue":"12 rue des Lois","adresse_code_postal":"31000","adresse_ville":"Toulouse","domaines":["insertion_emploi"],"nom_complet":"Claire Martin","fonction":"Conseillère en insertion","telephone":"0561000000","consent":true,"consent_donnees":true}' \
  -o /dev/null -w '%{http_code}\n'
docker compose logs backend --since 1m | grep "link for e2e-mails-2@test.fr\|mail to"
```

Expected: `201`, a `link for e2e-mails-2@test.fr` line, and **no** `mail to` line yet — the address is unproven.

Verify it — twice, the second time being a plain login:

```bash
curl -s -X POST http://localhost:8080/api/auth/verify-email -H 'Content-Type: application/json' \
  -d '{"token":"<TOKEN2>","password":"motdepasse-e2e2"}' -o /dev/null -w '%{http_code}\n'
docker compose logs backend --since 1m | grep -c "mail to"
curl -s -X POST http://localhost:8080/api/auth/verify-email -H 'Content-Type: application/json' \
  -d '{"token":"<TOKEN2>","password":"motdepasse-e2e2"}' -o /dev/null -w '%{http_code}\n'
docker compose logs backend --since 1m | grep -c "mail to"
```

Expected: `200`; a count equal to the number of admin addresses the SELECT listed (`e2e-mails-1@test.fr` among them); `200` again; the **same** count — nobody is told twice.

- [ ] **Step 9: E2E — the revocation mail**

In one shell call (the cookie jar goes in your session scratchpad directory):

```bash
JAR="<your scratchpad dir>/e2e-admin.jar"
curl -s -c "$JAR" -X POST http://localhost:8080/api/auth/login -H 'Content-Type: application/json' \
  -d '{"email":"e2e-mails-1@test.fr","password":"nouveau-mdp-e2e1"}' -o /dev/null -w '%{http_code}\n'
PID=$(curl -s -b "$JAR" 'http://localhost:8080/api/admin/counselor-applications?status=pending' \
  | python3 -c "import json,sys; print(next(a['id'] for a in json.load(sys.stdin)['applications'] if a['user']['email']=='e2e-mails-2@test.fr'))")
curl -s -b "$JAR" -X POST "http://localhost:8080/api/admin/counselor-applications/$PID/approve" \
  -H 'Content-Type: application/json' -d '{}' -o /dev/null -w '%{http_code}\n'
curl -s -b "$JAR" -X POST "http://localhost:8080/api/admin/counselor-applications/$PID/revoke" \
  -H 'Content-Type: application/json' -d '{"reason":"Fin de convention."}' -o /dev/null -w '%{http_code}\n'
docker compose logs backend --since 1m | grep "mail to e2e-mails-2@test.fr"
```

Expected: `200`, `200`, `200`, then two lines for `e2e-mails-2@test.fr` — the approval (existing mail) and the revocation (new).

Put the test admin back:

```bash
docker compose exec -T db mysql -uneoori -pneoori_dev neoori -e "UPDATE users SET role='candidate' WHERE email='e2e-mails-1@test.fr';"
```

- [ ] **Step 10: Final state**

Run: `git status --short && git log --oneline initial..HEAD`
Expected: a clean tree apart from the untracked `DOC-20260725-WA0000..pdf` (not ours; leave it), and on the branch the spec commit, the plan commit, and the seven task commits.

Report to the developer:
- the branch `feat/transactional-mails` and its test count;
- the E2E results (Steps 6–9), with the Step 6 screenshot;
- the seven mails as printed in Step 4;
- the four spec amendments at the top of this plan;
- that merging into `initial` and pushing deploys — the developer's call. Production already has `RESEND_API_KEY`, `MAIL_FROM` and `APP_URL` (checked 2026-10-01); this branch needs no migration and no new env var.
