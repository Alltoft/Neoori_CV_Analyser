import os
import re

from flask import Blueprint, current_app, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, verify_jwt_in_request
from ..extensions import db
from ..models.analysis import Analysis
from ..models.counselor_code import CounselorCode
from ..models.price_feedback import BUCKETS, PriceFeedback
from ..models.profile import Profile, prompt_context
from ..models.voyage import Voyage
from ..services.voyage.scoring import STAGE_S0, STAGE_VALIDATED
from ..services.voyage.scoring import prompt_context as voyage_prompt_context
from ..utils.tokens import generate_share_token
from ..utils.request_body import json_object, text_field, dict_field
from ..services import section_registry as registry
from ..services import tiers
from ..services.anthropic_service import start_analysis
from ..services.unlock_service import unlock_analysis

analyses_bp = Blueprint("analyses", __name__)

# ── TEMPORARY: force every analysis to one tier ──────────────────────────────
# While the PM reviews report *content*, the free tier's three sections aren't
# what needs judging — so every analysis runs paid until they're done.
#
# To restore normal behaviour: change the default below to "" (or set
# FORCE_ANALYSIS_TIER="" on Render). The paywall, the unlock flow and the
# Premium checkout are untouched — this only decides what a *new* analysis
# generates.
_FORCE_TIER = tiers.normalize(os.getenv("FORCE_ANALYSIS_TIER", "paid")) \
    if os.getenv("FORCE_ANALYSIS_TIER", "paid") else None

# Parcours 1 splits in two (Parcours doc §4). Chemin A is an actual job ad,
# pasted or uploaded — the report compares the CV against it point by point.
# Chemin B is the person's own description of a target, which the report has to
# announce as such: no sector lookup runs at launch (PM ruling), so nothing in
# it is sourced and the opening note says so.
CHEMIN_OFFRE = "A"
CHEMIN_DESCRIPTION = "B"

# The doc puts the floor for a described target at 20 characters. A job ad that
# short is a paste that went wrong, so chemin A keeps the original 50.
CIBLE_MIN = {CHEMIN_OFFRE: 50, CHEMIN_DESCRIPTION: 20}


def _normalize_chemin(value) -> str:
    """Coerce to a chemin, defaulting to the offer.

    Analyses written before the chemin was carried have no value, and their
    behaviour was chemin A — direct analysis, no framing note.
    """
    if str(value or "").strip().upper() == CHEMIN_DESCRIPTION:
        return CHEMIN_DESCRIPTION
    return CHEMIN_OFFRE


@analyses_bp.post("/")
def create_analysis():
    user_id = _optional_user_id()
    data = json_object()
    inputs = dict_field(data, "inputs")
    # normalize() maps the legacy 'A'/'B' codes onto parcours ids and falls
    # back to parcours 1 for anything unrecognised.
    path = registry.normalize(inputs.get("_path"))
    inputs["_path"] = path
    # Only parcours 1 has chemins; carrying the key elsewhere would be noise in
    # the stored inputs and in every prompt built from them.
    if path == "1":
        inputs["_chemin"] = _normalize_chemin(inputs.get("_chemin"))

    if _FORCE_TIER:
        # TEMPORARY — see _FORCE_TIER above. Delete the default to restore
        # normal tier selection.
        inputs["_tier"] = _FORCE_TIER
    elif path == "3":
        # Parcours 3 runs on the paid model for everyone — it serves the
        # populations the free tier exists to reach.
        inputs["_tier"] = tiers.PAID
    else:
        # normalize() accepts the legacy "haiku"/"sonnet" nicknames and
        # falls back to free for anything unrecognised.
        inputs["_tier"] = tiers.normalize(data.get("tier"))

    errors = VALIDATORS[path](inputs)
    if errors:
        return jsonify({"errors": errors}), 400

    # Fold in the Profil de base so the parcours forms never re-ask what the
    # profile already knows, and pre-shape bloc 5 into the three lists the
    # report may use — the raw answers never reach the model.
    _merge_profile(inputs, user_id)

    analysis = Analysis(
        user_id=user_id,
        inputs=inputs,
        status="queued",
        share_token=generate_share_token(),
        # Set by _merge_voyage a few lines up. Stored on the row as well as
        # in the inputs blob so "which voyage fed this analysis" survives a
        # JSON shape change and is queryable -- B2G traceability, as with
        # prompt_version_id.
        voyage_id=inputs.get("_voyage_id"),
    )
    db.session.add(analysis)
    db.session.commit()

    # Hand the slow Anthropic call to a background thread so the HTTP
    # response returns immediately. The frontend polls GET /analyses/<id>
    # for status — avoids edge-proxy timeouts on long Sonnet generations.
    start_analysis(analysis.id, current_app._get_current_object())

    return jsonify({"analysis": analysis.to_dict()}), 201


@analyses_bp.post("/draft")
@jwt_required()
def save_draft():
    """Create or update a draft. Auth required — anonymous drafts would be
    orphaned (no user_id) and never visible in the user's space."""
    user_id = get_jwt_identity()
    data = json_object()
    # dict_field, not a bare data.get(): a non-dict "inputs" would be stored
    # as-is on the model, then crash Analysis.parcours -- called from
    # to_dict() a few lines below -- via (self.inputs or {}).get("_path").
    inputs = dict_field(data, "inputs")
    # text_field, not a bare data.get(): a non-string draft_id (a list, a
    # dict) reaching filter_by(id=draft_id) as a query parameter raises
    # sqlalchemy.exc.ProgrammingError ("type 'list' is not supported") --
    # no id is ever actually a list, so falling back to "no draft_id" (a new
    # draft) is the right answer, same as an absent one.
    draft_id = text_field(data, "draft_id")

    if draft_id:
        analysis = Analysis.query.filter_by(
            id=draft_id, user_id=user_id, status="draft"
        ).first()
        if analysis:
            analysis.inputs = inputs
            db.session.commit()
            return jsonify({"analysis": analysis.to_dict()}), 200

    analysis = Analysis(
        user_id=user_id,
        inputs=inputs,
        status="draft",
    )
    db.session.add(analysis)
    db.session.commit()
    return jsonify({"analysis": analysis.to_dict()}), 201


@analyses_bp.get("/")
@jwt_required()
def list_analyses():
    user_id = get_jwt_identity()
    analyses = (
        Analysis.query
        .filter_by(user_id=user_id)
        .order_by(Analysis.created_at.desc())
        .all()
    )
    return jsonify({"analyses": [a.to_dict() for a in analyses]}), 200


@analyses_bp.get("/<analysis_id>")
def get_analysis(analysis_id):
    """Poll status / fetch a result.

    Deliberately not @jwt_required: the anonymous flow (no account yet) has to
    poll its own analysis, and the phase-1 rebuild is what makes accounts
    mandatory. But an analysis that *has* an owner is readable only by that
    owner — previously any caller could read any analysis, inputs included:
    CV text, name, location, and the health context parcours 3 collects.
    """
    analysis = Analysis.query.get_or_404(analysis_id)
    if not _may_access(analysis):
        return jsonify({"error": "Accès non autorisé."}), 403
    return jsonify({"analysis": analysis.to_dict()}), 200


@analyses_bp.post("/<analysis_id>/unlock")
def unlock_with_code(analysis_id):
    """Redeem a counselor code: free paid-tier regeneration (Cap Emploi /
    France Travail beneficiaries). Payment unlocks go through /api/payments."""
    analysis = Analysis.query.get_or_404(analysis_id)
    if not _may_access(analysis):
        return jsonify({"error": "Accès non autorisé."}), 403
    data = json_object()

    # Accept "ABCD1234", "abcd 1234", "ABCD-1234"… — codes are 8 alnum chars
    raw = text_field(data, "code")
    code_str = re.sub(r"[^A-Za-z0-9]", "", raw).upper()
    if not code_str:
        return jsonify({"error": "Code requis."}), 400

    code = CounselorCode.query.filter_by(code=code_str).first()
    if not code or not code.is_active:
        return jsonify({"error": "Code invalide ou désactivé."}), 400

    ok, reason = unlock_analysis(analysis, method="code")
    if not ok:
        return jsonify({"error": reason}), 409

    code.uses_count += 1
    db.session.commit()
    return jsonify({"analysis": analysis.to_dict()}), 200


@analyses_bp.post("/<analysis_id>/price-feedback")
def submit_price_feedback(analysis_id):
    """Willingness-to-pay probe, shown after a free report.

    Idempotent per analysis: re-answering replaces the previous answer rather
    than stacking, so one person can't skew the distribution by resubmitting.
    """
    analysis = Analysis.query.get_or_404(analysis_id)
    if not _may_access(analysis):
        return jsonify({"error": "Accès non autorisé."}), 403

    data = json_object()
    bucket = text_field(data, "bucket")
    if bucket not in BUCKETS:
        return jsonify({"error": "Réponse invalide."}), 400

    row = PriceFeedback.query.filter_by(analysis_id=analysis_id).first()
    if row is None:
        row = PriceFeedback(analysis_id=analysis_id, bucket=bucket)
        db.session.add(row)
    row.bucket = bucket
    if "useful" in data:
        row.useful = bool(data.get("useful"))
    db.session.commit()
    return jsonify({"feedback": row.to_dict()}), 200


@analyses_bp.delete("/<analysis_id>")
def delete_analysis(analysis_id):
    analysis = Analysis.query.get_or_404(analysis_id)
    if not _may_access(analysis):
        return jsonify({"error": "Accès non autorisé."}), 403

    db.session.delete(analysis)
    db.session.commit()
    return jsonify({"message": "Analyse supprimée."}), 200


# ── helpers ───────────────────────────────────────────────────────────────────

def _merge_profile(inputs: dict, user_id: str | None) -> None:
    """Copy the Profil de base and le voyage into this analysis's inputs.

    The ordinary profile fields are copied so the analysis stays readable on
    its own (a later profile edit must not silently rewrite an already-
    delivered report). Bloc 5 is reduced to prompt_context() first, and the
    OETH flag becomes a plain boolean — neither the raw condition answers nor
    the status itself is ever stored on the analysis.

    The voyage fold runs whether or not a profile exists, and whether or not
    there is a user_id at all: _merge_voyage is the only place that strips a
    client-supplied _voyage/_voyage_id (see its docstring), and that has to
    happen for every request this route accepts, anonymous ones included —
    create_analysis has no @jwt_required.
    """
    if user_id:
        profile = Profile.query.filter_by(user_id=user_id).first()
        if profile is not None:
            for field in ("prenom", "nom", "ville", "rayon", "tranche_age",
                          "situation", "reconversion_scope", "projet",
                          "contraintes_pratiques"):
                inputs.setdefault(field, getattr(profile, field, None))

            sensitive = profile.sensitive
            if sensitive is not None:
                inputs["_conditions"] = prompt_context(sensitive.conditions)
                inputs["_oeth"] = sensitive.oeth

    _merge_voyage(inputs, user_id)


def _merge_voyage(inputs: dict, user_id: str | None) -> None:
    """Fold le voyage into this analysis's inputs, reduced to plain lines.

    The first two statements remove whatever the caller itself posted under
    these keys. `inputs` is dict_field(data, "inputs") — a shallow copy of
    the request's own JSON, so it carries any key the client sent, verbatim.
    _voyage and _voyage_id are server-only: left in place, a posted _voyage
    reaches the model under the real "CE QUE LE VOYAGE A REVELE" header
    (prompt injection, and a framework-vocabulary leak past every guard
    prompt_context() enforces), and a posted _voyage_id either stamps another
    user's voyage onto this row's traceability column or, if it names no
    row, raises an uncaught IntegrityError on the Analysis(voyage_id=...)
    commit below — a 500 on a route anyone can call, logged in or not.
    Popping unconditionally, before any lookup, closes both — for every
    caller, which is why this runs even when user_id is falsy rather than
    from inside the `if user_id:` block above.

    Reduced here rather than at prompt-build time, exactly like bloc 5: the
    stored lines are what the model saw, so unlocking this analysis months
    later regenerates it from the same material instead of from whatever the
    person's voyage has become since.

    Two stages, and the narrow one is the default. Until a counselor has
    validated the portrait, only session 0 travels -- its phrase and its
    three attractions, which the person has already read on their own
    screen. Everything else waits for the restitution the paper protocol
    makes a human act. An analysis is not allowed to perform it first.

    No voyage: no key. Every parcours runs identically without one, and an
    empty key would be a shape every later reader has to allow for.
    """
    inputs.pop("_voyage", None)
    inputs.pop("_voyage_id", None)

    voyage = Voyage.for_prompt(user_id)
    if voyage is None:
        return

    stage = STAGE_VALIDATED if voyage.portrait_status == "validated" else STAGE_S0
    inputs["_voyage_id"] = voyage.id
    inputs["_voyage"] = voyage_prompt_context(
        voyage.synthesis(), voyage.micro_phrase, stage
    )


def _may_access(analysis: Analysis) -> bool:
    """Owner-only once an analysis has an owner.

    An ownerless (anonymous) analysis stays reachable by anyone holding its
    id — the UUID4 *is* the capability there, and there is no account to check
    against. Phase 1 makes accounts mandatory, at which point the ownerless
    branch is dead code and this collapses to a plain ownership test.
    """
    if analysis.user_id is None:
        return True
    return analysis.user_id == _optional_user_id()


def _optional_user_id() -> str | None:
    """Return current user id if a valid JWT is present, else None."""
    try:
        verify_jwt_in_request(optional=True)
        return get_jwt_identity()
    except Exception:
        return None


def _validate_inputs(inputs: dict) -> list[str]:
    """Parcours 1 — a CV and a target, and nothing else.

    Identity, age, location, situation and mobility used to be required here.
    They are fields of the Profil de base, folded in by _merge_profile, and
    `type_mobilite` no longer exists at all — the CDC v1.2 profile merged it
    into `situation`. Requiring them meant a form that asked twice and a
    validator that could reject an analysis over a field the data model had
    already deleted.
    """
    errors = []

    # text_field, not (inputs.get(...) or "").strip(): a hostile inputs.*
    # sub-field (a list, a dict) is truthy and survived the `or ""` as-is,
    # crashing on .strip() -- an unhandled 500 from a field one level below
    # the "inputs" guard in create_analysis.
    has_cv = text_field(inputs, "cv_text")
    if len(has_cv) < 200:
        errors.append("CV trop court (minimum 200 caractères).")

    minimum = CIBLE_MIN[_normalize_chemin(inputs.get("_chemin"))]
    cible = text_field(inputs, "cible_visee")
    if len(cible) < minimum:
        errors.append(f"Cible visée trop courte (minimum {minimum} caractères).")

    return errors


# ── per-parcours validation ──────────────────────────────────────────────────
# Each parcours asks for different things. Keeping the rules in one table
# rather than nested branches means adding a parcours is a new entry, not a
# new `if` inside three functions.

def _missing(inputs: dict, field: str, label: str, minimum: int = 1) -> str | None:
    value = text_field(inputs, field)
    if len(value) < minimum:
        if minimum > 1:
            return f"{label} — réponse trop courte ({minimum} caractères minimum)."
        return f"{label} — réponse requise."
    return None


def _validate_inputs_p2(inputs: dict) -> list[str]:
    """Parcours 2 — a CV (or a raw list of experiences) plus 3 questions.

    Three, not four: constraints live in bloc 4 of the profile and health is
    covered for everyone by bloc 5, so the fourth question was re-asking what
    the profile already knew.
    """
    errors = []
    if len(text_field(inputs, "cv_text")) < 200:
        errors.append("CV ou liste d'expériences trop courte (200 caractères minimum).")
    for field, label in (
        ("satisfaction", "Ce qui vous a donné le plus de satisfaction"),
        ("refus", "Ce que vous ne voulez plus faire"),
        ("raison_changement", "La raison principale de votre changement"),
    ):
        if err := _missing(inputs, field, label, minimum=20):
            errors.append(err)
    return errors


def _validate_inputs_p3(inputs: dict) -> list[str]:
    """Parcours 3 — no CV. The five life questions are the input."""
    errors = []
    for field, label in (
        ("experiences", "Ce que vous avez fait jusqu'à présent"),
        ("aime_faire", "Ce que vous aimez faire"),
        ("refus", "Ce que vous ne voulez pas ou ne pouvez pas faire"),
        ("contraintes", "Vos contraintes pratiques"),
        ("bon_travail", "Ce qu'est un bon travail pour vous"),
    ):
        # Deliberately lower than parcours 2: this parcours exists for people
        # who don't have a CV, and a long-answer requirement is exactly the
        # kind of barrier it is meant to remove.
        if err := _missing(inputs, field, label, minimum=10):
            errors.append(err)
    return errors


VALIDATORS = {
    "1": _validate_inputs,
    "2": _validate_inputs_p2,
    "3": _validate_inputs_p3,
}
