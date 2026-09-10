"""Le voyage — the candidate's six sessions and the counselor's sheet.

Two audiences, two access rules, one blueprint:

  * candidate handlers are owner-scoped. They resolve the caller's own current
    voyage and never take an id from the client, so there is nothing to
    enumerate and no ownership check to forget.
  * counselor handlers need the counselor/admin role **and** the share token.
    That is deliberately stricter than /api/c/<token> for analyses: the
    synthesis sheet is a psychometric read-out, so a leaked link alone must
    not open it (spec § Security).

Session locking is enforced here and not only in the UI — see
models.voyage.session_lock: S0 needs the voyage to exist, S1-S5 need a
counselor code and a Profil de base with prénom + tranche d'âge, and every
session needs the one before it.
"""
import re
from datetime import datetime

from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from ..extensions import db
from ..models.counselor_code import CounselorCode
from ..models.profile import Profile
from ..models.voyage import (
    CONSENT_VERSION,
    LOCK_ORDER,
    PORTRAIT_KEYS,
    STATUS_EN_COURS,
    STATUS_S0,
    STATUS_TERMINE,
    Voyage,
    VoyageNote,
    session_lock,
)
from ..services.voyage import bank, scoring
from ..utils.decorators import role_required
from ..utils.tokens import generate_share_token

voyage_bp = Blueprint("voyage", __name__)

# The API's fixed French strings. app.url_map.strict_slashes is False globally,
# so "" also answers "/" — do not add per-route slash handling.
NO_VOYAGE = "Aucun voyage en cours."


def _current() -> Voyage | None:
    """The caller's own voyage: the open one, else the last one played."""
    return Voyage.current_for(get_jwt_identity())


def _profile() -> Profile | None:
    return Profile.query.filter_by(user_id=get_jwt_identity()).first()


# ── candidate ────────────────────────────────────────────────────────────────

@voyage_bp.get("/bank")
@jwt_required()
def get_bank():
    """The question bank, text only.

    bank.public() strips every scoring key at every depth. The mapping from an
    option to a trait is the product and the counselor manual is confidential,
    so it never crosses this line.
    """
    return jsonify({"bank": bank.public()}), 200


@voyage_bp.get("")
@jwt_required()
def get_voyage():
    voyage = _current()
    return jsonify({"voyage": voyage.to_dict() if voyage else None}), 200


@voyage_bp.post("")
@jwt_required()
def create_voyage():
    """Start a voyage. Both boxes are mandatory and both are recorded.

    Consent is a separate record from the profile's: a psychometric profile is
    not covered by consent given for a CV analysis. The age attestation is the
    French digital-consent floor; under-15 parental consent is out of scope for
    v1 (spec decision 13).
    """
    data = request.get_json(silent=True)
    data = data if isinstance(data, dict) else {}
    errors = []
    if data.get("consent") is not True:
        errors.append("Le consentement est requis.")
    if data.get("age_attested") is not True:
        errors.append("Vous devez attester avoir 15 ans ou plus.")
    if errors:
        return jsonify({"errors": errors}), 400

    user_id = get_jwt_identity()
    if Voyage.open_for(user_id) is not None:
        return jsonify({"error": "Un voyage est déjà en cours."}), 409

    voyage = Voyage(
        user_id=user_id,
        status=STATUS_EN_COURS,
        sessions_completed=[],
        consent_at=datetime.utcnow(),
        consent_version=CONSENT_VERSION,
        age_attested=True,
        scoring_version=bank.SCORING_VERSION,
    )
    db.session.add(voyage)
    db.session.commit()
    return jsonify({"voyage": voyage.to_dict()}), 201


@voyage_bp.delete("")
@jwt_required()
def delete_voyage():
    """RGPD erasure, independent of the profile in both directions.

    Erases the current voyage (§ E9:1175) and its counselor notes, cascade-
    deleted with the row. An earlier, already-finished voyage from a retake is
    untouched: it keeps existing with its own share token, so
    GET /api/voyage/c/<its token> still serves it to a counselor. Not a 404
    when there is nothing to erase: mirrors delete_profile.
    """
    voyage = _current()
    if voyage is None:
        return jsonify({"message": "Aucun voyage à supprimer."}), 200
    db.session.delete(voyage)
    db.session.commit()
    return jsonify({"message": "Voyage supprimé."}), 200


def _session_of(item_id: str) -> str:
    """"S0-01" -> "0", "S3-7" -> "3". Every bank id is S<n>-<k>."""
    return item_id[1]


@voyage_bp.get("/responses")
@jwt_required()
def get_responses():
    """The person's own answers, for resuming a session or re-rendering it."""
    voyage = _current()
    if voyage is None:
        return jsonify({"error": NO_VOYAGE}), 404
    return jsonify({"responses": voyage.responses}), 200


@voyage_bp.put("/responses")
@jwt_required()
def put_responses():
    """Merge answers and exit tickets into the voyage.

    Merge, not replace: the player saves on every « Suivant », so a lost
    connection costs one scene rather than a session. Unknown ids are dropped
    silently — a client one deploy behind must not lose a whole save over an
    item that moved — but a known id carrying a value the bank rejects is a
    400, because that means the two have genuinely drifted.
    """
    voyage = _current()
    if voyage is None:
        return jsonify({"error": NO_VOYAGE}), 404

    data = request.get_json(silent=True)
    if data is not None and not isinstance(data, dict):
        # A body that parsed as valid JSON but the wrong top-level shape (an
        # array, a bare string, a number) is refused outright — treating it
        # like {} here would hide a client bug behind a silent no-op. An
        # absent or unparseable body stays a no-op (data is None -> {}),
        # matching the "empty PUT" contract the tests rely on.
        return jsonify({"error": "Corps de requête invalide."}), 400
    data = data or {}
    raw_answers = data.get("answers")
    raw_billets = data.get("billets")
    answers = raw_answers if isinstance(raw_answers, dict) else {}
    billets = raw_billets if isinstance(raw_billets, dict) else {}

    known = {i: v for i, v in answers.items() if bank.item(i) is not None}

    # Locks are checked over every session the request touches, before any
    # merge — a refusal must leave the row exactly as it was.
    touched = {_session_of(i) for i in known}
    touched |= {n for n in billets if n in bank.SESSION_IDS}
    profile = _profile()
    for n in sorted(touched):
        lock = session_lock(voyage, profile, n)
        if lock:
            return jsonify({"error": lock}), 403

    invalid = [
        f"Réponse invalide pour {i}."
        for i, value in sorted(known.items())
        if not bank.validate_answer(i, value)
    ]
    if invalid:
        return jsonify({"errors": invalid}), 400

    merged = voyage.responses
    merged["answers"].update(known)
    for n, fields in billets.items():
        if n not in bank.SESSION_IDS or not isinstance(fields, dict):
            continue
        allowed = set(bank.billet_keys(n))
        target = dict(merged["billets"].get(n) or {})
        for key, value in fields.items():
            if key not in allowed:
                continue
            if value is None:
                target[key] = ""
            elif isinstance(value, (str, int, float, bool)):
                # A scalar is what a person can type; anything else (a dict, a
                # list) is dropped rather than stringified — the billet text
                # is quoted into the portrait prompt as the candidate's own
                # words, so `str({'nested': 'x'})` must never reach it looking
                # like something a person wrote. Same disposal rule as an
                # unknown field key (contract § E5).
                target[key] = str(value)
        merged["billets"][n] = target

    voyage.responses = merged
    db.session.commit()
    return jsonify({"responses": voyage.responses}), 200


# ── generation seam ──────────────────────────────────────────────────────────
# The two spawn points live behind these two functions for two reasons: tests
# monkeypatch them by name (app.routes.voyage._spawn_micro), the way
# test_unlock.py patches app.services.unlock_service.start_analysis; and the
# import is late, so this phase ships before services/voyage/generation.py
# exists. Phase 2 creates that module with start_micro(voyage_id, app) /
# start_portrait(voyage_id, app) and nothing here changes.

def _spawn_micro(voyage_id: str) -> None:
    try:
        from ..services.voyage import generation
    except ImportError:
        current_app.logger.info("voyage: generation service absent, micro not spawned")
        return
    generation.start_micro(voyage_id, current_app._get_current_object())


def _spawn_portrait(voyage_id: str) -> None:
    try:
        from ..services.voyage import generation
    except ImportError:
        current_app.logger.info("voyage: generation service absent, portrait not spawned")
        return
    generation.start_portrait(voyage_id, current_app._get_current_object())


@voyage_bp.post("/sessions/<n>/complete")
@jwt_required()
def complete_session(n):
    """Close a session.

    Everything the session asks must be answered — the billet is optional, the
    items are not. S0 flips the status and asks for the phrase; S5 finishes the
    voyage, mints the share token the person hands to their counselor, and asks
    for the portrait. Sessions 1-4 change no status.
    """
    if n not in bank.SESSION_IDS:
        return jsonify({"error": "Session inconnue."}), 400

    voyage = _current()
    if voyage is None:
        return jsonify({"error": NO_VOYAGE}), 404

    done = list(voyage.sessions_completed or [])
    if n in done:
        return jsonify({"error": "Cette session est déjà terminée."}), 409

    lock = session_lock(voyage, _profile(), n)
    if lock == LOCK_ORDER:
        # Out of order is a state conflict, not a permission problem.
        return jsonify({"error": LOCK_ORDER}), 409
    if lock:
        return jsonify({"error": lock}), 403

    missing = scoring.missing_items(voyage.responses, n)
    if missing:
        return jsonify({"errors": ["Réponses manquantes.", *missing]}), 400

    # JSON column: reassign a new list. Appending in place leaves SQLAlchemy
    # unaware of the change (the same trap as unlock_service's dict(inputs)).
    voyage.sessions_completed = done + [n]

    spawn = None
    if n == "0":
        voyage.status = STATUS_S0
        voyage.micro_status = "generating"
        spawn = "micro"
    elif n == "5":
        voyage.status = STATUS_TERMINE
        voyage.completed_at = datetime.utcnow()
        voyage.share_token = generate_share_token()
        voyage.portrait_status = "generating"
        spawn = "portrait"

    db.session.commit()

    # After the commit: the background run re-queries the row on its own
    # connection, so it must already be there to find.
    if spawn == "micro":
        _spawn_micro(voyage.id)
    elif spawn == "portrait":
        _spawn_portrait(voyage.id)

    return jsonify({"voyage": voyage.to_dict()}), 200


@voyage_bp.post("/unlock")
@jwt_required()
def unlock_voyage():
    """Redeem a counselor code: it opens S1-S5.

    Free access for Cap Emploi / Mission Locale / France Travail beneficiaries,
    the same mechanism that unlocks a paid analysis. If the voyage is ever
    sold, the gate moves to this one function.

    The « already unlocked » check runs first so a second redemption cannot
    burn a use off a second code.
    """
    voyage = _current()
    if voyage is None:
        return jsonify({"error": NO_VOYAGE}), 404
    if voyage.counselor_code_id:
        return jsonify({"error": "Ce voyage est déjà débloqué."}), 409

    # request.get_json(silent=True) or {} lets a JSON array or a bare string
    # survive as truthy, and the next .get() call then raises AttributeError
    # -> an unhandled 500 (the defect put_responses above was fixed for).
    # Coerce any non-dict body to {} instead, so it falls through to the
    # ordinary "code missing" 400 below.
    data = request.get_json(silent=True)
    data = data if isinstance(data, dict) else {}

    # Same guard for the field itself: a non-string "code" (an int, a list, a
    # dict) must not reach .strip() and raise AttributeError either.
    raw_code = data.get("code")
    raw_code = raw_code if isinstance(raw_code, str) else ""
    # Accept "ABCD1234", "abcd 1234", "ABCD-1234"… — same normalisation as
    # analyses.unlock_with_code, because it is the same code on the same card.
    code_str = re.sub(r"[^A-Za-z0-9]", "", raw_code.strip()).upper()
    if not code_str:
        return jsonify({"error": "Code requis."}), 400

    code = CounselorCode.query.filter_by(code=code_str).first()
    if not code or not code.is_active:
        return jsonify({"error": "Code invalide ou désactivé."}), 400

    voyage.counselor_code_id = code.id
    code.uses_count += 1
    db.session.commit()
    return jsonify({"voyage": voyage.to_dict()}), 200


@voyage_bp.get("/portrait")
@jwt_required()
def get_portrait():
    """The six sections — only once a counselor has validated them.

    Before that the person sees « en attente de validation » and keeps S0's
    phrase. The draft, the synthesis snapshot and the leak flags are the
    counselor's working material and never cross to this side.
    """
    voyage = _current()
    if voyage is None:
        return jsonify({"error": NO_VOYAGE}), 404
    if voyage.portrait_status != "validated":
        return jsonify({
            "error": "Votre portrait est en attente de validation.",
            "status": voyage.portrait_status,
        }), 409
    return jsonify({"portrait": {
        "sections": voyage.portrait_sections,
        "validated_at": (
            voyage.portrait_validated_at.isoformat()
            if voyage.portrait_validated_at else None
        ),
    }}), 200


# ── counselor ────────────────────────────────────────────────────────────────
# Role AND token. /api/c/<token> for an analysis is public by design — a
# counselor opens the link without an account. The synthesis sheet is a
# psychometric read-out, so a leaked link alone must not open it.

NOT_FOUND = "Voyage introuvable."


def _counselor_portrait(voyage: Voyage) -> dict:
    """The five-key shape every counselor portrait response returns.

    Deliberately narrow: the snapshot, the token counts, the prompt version and
    the stored error stay inside the ciphertext where they were written.
    """
    payload = voyage.portrait or {}
    sections = payload.get("sections") or {}
    return {
        "status": voyage.portrait_status,
        "sections": {k: v for k, v in sections.items() if k in PORTRAIT_KEYS},
        "flags": list(payload.get("flags") or []),
        "edited": bool(payload.get("edited")),
        "validated_at": (
            voyage.portrait_validated_at.isoformat()
            if voyage.portrait_validated_at else None
        ),
    }


@voyage_bp.get("/c/<token>")
@role_required("counselor", "admin")
def counselor_sheet(token):
    """The page-18 synthesis sheet plus the portrait draft.

    The synthesis is recomputed from the answers on every read, so a corrected
    scoring table takes effect without a migration. The 5-phase restitution
    guide is static frontend content and is not served here.
    """
    voyage = Voyage.by_token(token)
    if voyage is None:
        return jsonify({"error": NOT_FOUND}), 404

    profile = Profile.query.filter_by(user_id=voyage.user_id).first()
    return jsonify({"voyage": {
        "id": voyage.id,
        "status": voyage.status,
        "prenom": getattr(profile, "prenom", None),
        "tranche_age": getattr(profile, "tranche_age", None),
        "situation": getattr(profile, "situation", None),
        "synthesis": voyage.synthesis(),
        "portrait": _counselor_portrait(voyage),
    }}), 200


@voyage_bp.put("/c/<token>/portrait")
@role_required("counselor", "admin")
def counselor_edit_portrait(token):
    """Replace all six sections. Allowed while draft or validated — a
    correction made during the restitution session must not force the
    counselor to un-validate the portrait in front of the person."""
    voyage = Voyage.by_token(token)
    if voyage is None:
        return jsonify({"error": NOT_FOUND}), 404
    if voyage.portrait_status not in ("draft", "validated"):
        return jsonify({"error": "Aucun portrait à modifier."}), 409

    # request.get_json(silent=True) or {} lets a JSON array or a bare string
    # survive as truthy, and the next .get() call then raises AttributeError
    # -> an unhandled 500 (the same defect fixed in put_responses/unlock_voyage
    # above). Coerce any non-dict body to {} instead, so an array body falls
    # through to the ordinary "sections missing" 400 below.
    data = request.get_json(silent=True)
    data = data if isinstance(data, dict) else {}
    raw = data.get("sections")
    sections = raw if isinstance(raw, dict) else {}

    errors = [f"Section inconnue : {key}." for key in sorted(sections)
              if key not in PORTRAIT_KEYS]
    # A dict or a list is truthy and survives str(value or "").strip() as
    # non-empty, so the "manquante ou vide" check alone would let it through
    # -- and the assignment below would then store str({'nested': 'x'}) and
    # serve it to the candidate as their own portrait text. Unlike
    # put_responses's billets (:209-216), which only feed a prompt, this is
    # rendered straight to the person, so a non-string value is refused
    # outright rather than dropped or stringified.
    for key in PORTRAIT_KEYS:
        value = sections.get(key)
        if key in sections and not isinstance(value, str):
            errors.append(f"Section invalide : {key}.")
        elif not (value or "").strip():
            errors.append(f"Section manquante ou vide : {key}.")
    if errors:
        return jsonify({"errors": errors}), 400

    payload = dict(voyage.portrait or {})
    payload["sections"] = {key: str(sections[key]).strip() for key in PORTRAIT_KEYS}
    payload["edited"] = True
    voyage.portrait = payload
    db.session.commit()
    return jsonify({"portrait": _counselor_portrait(voyage)}), 200


@voyage_bp.post("/c/<token>/portrait/regenerate")
@role_required("counselor", "admin")
def counselor_regenerate_portrait(token):
    """Re-run the portrait call. Draft only: a validated portrait has been
    restituted and must not change under the person's feet."""
    voyage = Voyage.by_token(token)
    if voyage is None:
        return jsonify({"error": NOT_FOUND}), 404
    if voyage.portrait_status != "draft":
        return jsonify({"error": "Le portrait ne peut plus être régénéré."}), 409

    voyage.portrait_status = "generating"
    db.session.commit()
    _spawn_portrait(voyage.id)
    # The stored sections are about to be overwritten, so the response reports
    # the run rather than the text that is on its way out.
    return jsonify({"portrait": {
        "status": "generating", "sections": {}, "flags": [],
        "edited": False, "validated_at": None,
    }}), 202


@voyage_bp.post("/c/<token>/validate")
@role_required("counselor", "admin")
def counselor_validate_portrait(token):
    """« Valider et transmettre » — the step that opens the portrait to the
    candidate. Who did it and when are both recorded.

    Refuses a draft with an incomplete section set (⚑ guard added here, not
    in the brief or the contract): get_portrait exposes sections only once
    portrait_status == "validated", with no completeness check of its own —
    validating an incomplete draft would hand the candidate a 200 with
    empty/partial `sections` and nothing to say it went wrong. Reuses
    Voyage.portrait_sections, which is already {} unless all six
    PORTRAIT_KEYS are present and non-empty (models/voyage.py).
    """
    voyage = Voyage.by_token(token)
    if voyage is None:
        return jsonify({"error": NOT_FOUND}), 404
    if voyage.portrait_status != "draft":
        return jsonify({"error": "Aucun portrait à valider."}), 409
    if not voyage.portrait_sections:
        return jsonify({"error": "Le portrait est incomplet : impossible de le valider."}), 409

    voyage.portrait_status = "validated"
    voyage.portrait_validated_at = datetime.utcnow()
    voyage.validated_by_id = get_jwt_identity()
    db.session.commit()
    return jsonify({"portrait": _counselor_portrait(voyage)}), 200


@voyage_bp.get("/c/<token>/notes")
@role_required("counselor", "admin")
def get_voyage_note(token):
    """This counselor's own note. Never shown to the candidate."""
    voyage = Voyage.by_token(token)
    if voyage is None:
        return jsonify({"error": NOT_FOUND}), 404
    note = VoyageNote.query.filter_by(
        voyage_id=voyage.id, counselor_id=get_jwt_identity()
    ).first()
    return jsonify({"note": note.to_dict() if note else None}), 200


@voyage_bp.put("/c/<token>/notes")
@role_required("counselor", "admin")
def upsert_voyage_note(token):
    """Upsert keyed on (voyage_id, counselor_id) — every counselor keeps
    their own private note on the same voyage; nobody reads another's."""
    voyage = Voyage.by_token(token)
    if voyage is None:
        return jsonify({"error": NOT_FOUND}), 404

    # A non-dict body (a JSON array, a bare string/number) must not crash
    # .get("body") into a 500 -- but it also must not be silently coerced to
    # "", which would wipe an existing note under a malformed request and
    # report it as a 200 success. Refuse it outright instead.
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Note invalide."}), 400

    # "" is the one falsy value that is a deliberate, explicit clear (§ E15) --
    # but only when the key is actually present. data.get("body", "") made an
    # absent "body" key indistinguishable from an explicit "", so a malformed
    # {} or a {"autre": "x"} silently wiped the note under a 200. Require the
    # key outright.
    if "body" not in data:
        return jsonify({"error": "Note invalide."}), 400

    # A "body" field present but not a string (an int, a list, a dict) is
    # refused the same way -- accepting it would either crash the Text
    # column or, if coerced, destroy the stored note under bad input.
    raw_body = data.get("body")
    if not isinstance(raw_body, str):
        return jsonify({"error": "Note invalide."}), 400

    counselor_id = get_jwt_identity()
    note = VoyageNote.query.filter_by(voyage_id=voyage.id, counselor_id=counselor_id).first()
    if note is None:
        note = VoyageNote(voyage_id=voyage.id, counselor_id=counselor_id)
        db.session.add(note)
    note.body = raw_body
    db.session.commit()
    return jsonify({"note": note.to_dict()}), 200
