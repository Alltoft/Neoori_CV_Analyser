import hmac
import os

from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity, verify_jwt_in_request
from ..extensions import db
from ..models.analysis import Analysis
from ..models.counselor_code import CounselorCode
from ..models.counselor_note import CounselorNote
from ..models.price_feedback import BUCKETS, PriceFeedback
from ..models.profile import Profile, prompt_context
from ..models.voyage import Voyage
from ..services.voyage.scoring import STAGE_S0, STAGE_VALIDATED
from ..services.voyage.scoring import prompt_context as voyage_prompt_context
from ..utils.tokens import generate_share_token, hash_token
from ..utils.request_body import json_object, text_field, dict_field
from ..services import code_service
from ..services import doors
from ..services import section_registry as registry
from ..services import tiers
from ..services import unlock_service
from ..services.anthropic_service import start_analysis

analyses_bp = Blueprint("analyses", __name__)

# The key to a no-login report travels in this header, never in a URL the
# server would log (four-doors spec, decision 30).
TOKEN_HEADER = "X-Analysis-Token"

# ── TEMPORARY: force every analysis to one tier ──────────────────────────────
# While the PM reviews report *content*, the free tier's three sections aren't
# what needs judging — so every analysis runs paid until they're done.
#
# To restore normal behaviour: change the default below to "" (or set
# FORCE_ANALYSIS_TIER="" in /srv/neoori/.env). The paywall, the unlock flow and the
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
@jwt_required()
def create_analysis():
    # An account with a proven address is required (email verification spec,
    # decision 13): the anonymous path made throwaway accounts unnecessary.
    user_id = get_jwt_identity()
    data = json_object()
    inputs = dict_field(data, "inputs")
    # Parcours 1 is the only parcours (2 and 3 were retired on 2026-10-08).
    # The stored id is the server's, whatever the body says: a stale page
    # posting "2" or "3" gets a parcours 1 analysis, validated as one.
    inputs["_path"] = registry.DEFAULT_PARCOURS
    inputs["_chemin"] = _normalize_chemin(inputs.get("_chemin"))

    if _FORCE_TIER:
        # TEMPORARY — see _FORCE_TIER above. Delete the default to restore
        # normal tier selection.
        inputs["_tier"] = _FORCE_TIER
    else:
        # normalize() accepts the legacy "haiku"/"sonnet" nicknames and
        # falls back to free for anything unrecognised.
        inputs["_tier"] = tiers.normalize(data.get("tier"))

    errors = _validate_inputs(inputs)
    if errors:
        return jsonify({"errors": errors}), 400

    # Fold in the Profil de base so the form never re-asks what the profile
    # already knows, and pre-shape bloc 5 into the three lists the report may
    # use — the raw answers never reach the model.
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
    # Same rule as create_analysis: a draft that names a parcours names
    # parcours 1. An absent _path already means parcours 1, so an empty draft
    # stays empty.
    if "_path" in inputs:
        inputs["_path"] = registry.DEFAULT_PARCOURS
    # text_field, not a bare data.get(): a non-string draft_id (a list, a
    # dict) reaching filter_by(id=draft_id) as a query parameter raises
    # sqlalchemy.exc.ProgrammingError ("type 'list' is not supported") --
    # no id is ever actually a list, so falling back to "no draft_id" (a new
    # draft) is the right answer, same as an absent one.
    draft_id = text_field(data, "draft_id")
    # Same rule as _merge_voyage: _voyage / _voyage_id are server-owned, never
    # client-supplied. A draft never sets them itself (voyage_id is only
    # assigned at create_analysis time), so a posted pair here can only be a
    # leftover echoed back from a previous submit response or a planted one --
    # pop both before the row is created or updated, covering both branches
    # below in one place.
    inputs.pop("_voyage", None)
    inputs.pop("_voyage_id", None)

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


@analyses_bp.get("/by-token")
def get_by_token():
    """A no-login report, by the key in its link. A held draft is read through
    /held, by its cookie: its key never leaves the cookie."""
    presented = _header_token_hash()
    row = Analysis.query.filter_by(access_token_hash=presented).first() if presented else None
    if row is None or row.status == "draft":
        return jsonify({"error": "Ce lien n'est plus valide."}), 404
    return jsonify({"analysis": row.to_dict()}), 200


@analyses_bp.get("/<analysis_id>")
def get_analysis(analysis_id):
    """Poll status / fetch a result.

    Not @jwt_required: a no-login report has no session to check, so it is
    read with its token header, and an ownerless row stays readable by id only
    when the four-doors migration marked it `legacy`. An analysis that *has*
    an owner is readable only by that owner — previously any caller could read
    any analysis, inputs included: CV text, name, location, and the bloc 5
    context folded in from the profile. _may_access has the whole order.
    """
    analysis = Analysis.query.get_or_404(analysis_id)
    if not _may_access(analysis):
        return jsonify({"error": "Accès non autorisé."}), 403
    return jsonify({"analysis": analysis.to_dict()}), 200


@analyses_bp.post("/<analysis_id>/unlock")
@jwt_required()
def unlock_with_code(analysis_id):
    """Redeem a promo code on the caller's own free report (four-doors spec,
    decision 22). A conseiller code is refused here: with one, the full report
    goes to the counselor through the advisor door, never back to the
    candidate (ruling 2).

    The unlock goes on the row before the redemption is written, so redeem()'s
    one commit carries both and the run starts only after it: a use is never
    spent on a report that stays free."""
    analysis = Analysis.query.get_or_404(analysis_id)
    user_id = get_jwt_identity()
    if analysis.user_id is None or analysis.user_id != user_id:
        return jsonify({"error": "Accès non autorisé."}), 403

    code_str = code_service.normalize(text_field(json_object(), "code"))
    if not code_str:
        return jsonify({"error": code_service.REQUIRED}), 400
    # The kind first: a spent or expired conseiller code still gets the
    # sentence that says where such a code goes, not « limite atteinte ».
    known = CounselorCode.query.filter_by(code=code_str).first()
    if known is not None and code_service.kind(known) != code_service.PROMO:
        return jsonify({"error": code_service.NOT_FOR_UNLOCK}), 409
    code, refusal = code_service.resolve(code_str, "analysis")
    if refusal:
        return jsonify({"error": refusal}), 400

    reason = unlock_service.refusal(analysis)
    if reason:
        return jsonify({"error": reason}), 409

    # The id goes in a local because a rollback inside redeem() expires the row.
    target_id = analysis.id
    unlock_service.apply_unlock(analysis, method="code")
    refused = code_service.redeem(code, user_id=user_id, target_type="analysis", target_id=target_id)
    if refused:
        # redeem() has rolled back on a key violation, but not on its early
        # EXHAUSTED: either way the pending unlock must not outlive the refusal.
        db.session.rollback()
        return jsonify({"error": refused}), 409

    # When another request took the slot first, redeem() rolls back and retries
    # once, and that retry commits only the redemption: the unlock rode on the
    # commit that was rolled back. Re-read the row and put it back — unless
    # someone else unlocked it meanwhile (a payment), which stays theirs.
    analysis = Analysis.query.get_or_404(target_id)
    if analysis.unlock_method != "code":
        reason = unlock_service.refusal(analysis)
        if reason:
            return jsonify({"error": reason}), 409
        unlock_service.apply_unlock(analysis, method="code")
        db.session.commit()

    unlock_service.start_run(target_id)
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

    # price_feedback's and counselor_notes' foreign keys carry no ON DELETE, so
    # a report someone rated, or a counselor annotated, cannot be deleted until
    # those rows are: without these two lines the delete is a 500.
    PriceFeedback.query.filter_by(analysis_id=analysis.id).delete()
    CounselorNote.query.filter_by(analysis_id=analysis.id).delete()
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

    The voyage fold runs whether or not a profile exists: _merge_voyage is
    the only place that strips a client-supplied _voyage/_voyage_id (see its
    docstring), and that has to happen for every request create_analysis
    accepts. That route is @jwt_required now, so user_id is always set there;
    the falsy branch is kept so the strip never depends on it.
    """
    if user_id:
        profile = Profile.query.filter_by(user_id=user_id).first()
        if profile is not None:
            for field in ("prenom", "nom", "ville", "rayon", "tranche_age",
                          "situation", "reconversion_scope", "projet",
                          "contraintes_pratiques",
                          # « Ton parcours » — answered inside the voyage,
                          # stored on the profile, folded in from here like
                          # every other block of the Profil de base.
                          "diplome", "type_etudes", "intitule_etudes",
                          "appetence_etudes"):
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
    commit below — a 500 any signed-in account could trigger.
    Popping unconditionally, before any lookup, closes both — for every
    caller, which is why this runs even when user_id is falsy rather than
    from inside _merge_profile's `if user_id:` block.

    Reduced here rather than at prompt-build time, exactly like bloc 5: the
    stored lines are what the model saw, so unlocking this analysis months
    later regenerates it from the same material instead of from whatever the
    person's voyage has become since.

    Two stages, and the narrow one is the default. Until a counselor has
    validated the portrait, only session 0 travels -- its phrase and its
    three attractions, which the person has already read on their own
    screen. Everything else waits for the restitution the paper protocol
    makes a human act. An analysis is not allowed to perform it first.

    No voyage: no key. An analysis runs identically without one, and an
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


def _header_token_hash() -> str | None:
    """The hash of the X-Analysis-Token header, or None. The page reads the
    token from its URL fragment and sends it here as a header, so it never
    lands in an access log (four-doors spec, decision 30)."""
    raw = request.headers.get(TOKEN_HEADER, "")
    return hash_token(raw) if raw else None


def _may_access(analysis: Analysis) -> bool:
    """Who may read or change an analysis on the candidate-facing routes —
    the spec's « Who may read an analysis », in its order.

    1. An advisor-door report is the counselor's alone (ruling 2), and its
       counselor reads it through /api/counselor, never here. `door` is tested
       as well as `counselor_id`, so erasing a counselor never opens one.
    2. A token row opens with its token, and only with it.
    3. An owned row opens for its owner.
    4. A legacy row — ownerless, written before accounts were required, marked
       by the four-doors migration — stays open by id, as it always was.
    5. Anything else is closed. A row that loses its owner some other way must
       not become readable by whoever has its id.
    """
    if analysis.door == doors.ADVISOR or analysis.counselor_id is not None:
        return False
    if analysis.access_token_hash is not None:
        presented = _header_token_hash()
        return presented is not None and hmac.compare_digest(presented, analysis.access_token_hash)
    if analysis.user_id is not None:
        return analysis.user_id == _optional_user_id()
    return analysis.door == doors.LEGACY


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
