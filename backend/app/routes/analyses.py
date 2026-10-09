import hmac
from datetime import datetime
from functools import partial
from uuid import uuid4

from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity, verify_jwt_in_request
from ..extensions import db
from ..models.analysis import Analysis
from ..models.counselor_code import CounselorCode
from ..models.counselor_note import CounselorNote
from ..models.price_feedback import BUCKETS, PriceFeedback
from ..models.profile import CONSENT_VERSION, Profile, prompt_context
from ..models.voyage import Voyage
from ..services.voyage.scoring import STAGE_S0, STAGE_VALIDATED
from ..services.voyage.scoring import prompt_context as voyage_prompt_context
from ..utils.tokens import hash_token, new_access_token
from ..utils.request_body import json_object, text_field, dict_field
from ..services import analysis_inputs, held
from ..services import code_service
from ..services import doors
from ..services import section_registry as registry
from ..services import unlock_service
from ..services.anthropic_service import start_analysis

analyses_bp = Blueprint("analyses", __name__)

# The key to a no-login report travels in this header, never in a URL the
# server would log (four-doors spec, decision 30).
TOKEN_HEADER = "X-Analysis-Token"

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
    """The submit behind « Générer mon analyse »: one of four doors (four-doors
    spec). services/doors.py decides the tier and who the report is for. A
    `tier` in the body, from a form older than the doors, is never read.

    Order matters: everything that can refuse runs before the code is spent,
    and the code is spent — committed — before the run starts (decision 23).
    At the doors with a code that commit is redeem()'s own, and it carries the
    row and its run_log entry with it, so a use is never spent on a run that
    has no row.
    """
    user_id = _optional_user_id()
    data = json_object()

    inputs, errors = analysis_inputs.clean(dict_field(data, "inputs"))
    if errors:
        return jsonify({"errors": errors}), 400

    plan, refusal = doors.decide(text_field(data, "door") or None, user_id=user_id)
    if refusal:
        message, status = refusal
        return jsonify({"error": message}), status

    # Parcours 1 is the only parcours (2 and 3 were retired on 2026-10-08), and
    # the stored id is the server's: clean() never lets a posted _path through.
    inputs["_path"] = registry.DEFAULT_PARCOURS
    inputs["_chemin"] = _normalize_chemin(inputs.get("_chemin"))
    errors = _validate_inputs(inputs)
    if errors:
        return jsonify({"errors": errors}), 400

    if plan.needs_identity:
        prenom, nom = text_field(data, "prenom"), text_field(data, "nom")
        if not prenom or not nom:
            return jsonify({"error": doors.IDENTITY}), 400
        if len(prenom) > doors.NAME_MAX or len(nom) > doors.NAME_MAX:
            return jsonify({"error": doors.IDENTITY_LONG}), 400
        inputs["prenom"], inputs["nom"] = prenom, nom

    if plan.needs_consent and data.get("consent") is not True:
        return jsonify({"error": doors.CONSENT}), 400

    over = doors.over_cap(plan, user_id)
    if over:
        return jsonify({"error": over}), 429

    code = None
    if plan.code_kind:
        code, door_refusal = code_service.resolve_for_door(data.get("code"), plan.door, user_id)
        if door_refusal:
            body = {"error": door_refusal.message}
            if door_refusal.door:
                body["door"] = door_refusal.door
            return jsonify(body), door_refusal.status

    inputs["_tier"] = plan.tier
    if plan.folds_profile:
        # Profil de base and le voyage join the inputs — account and promo
        # only. An advisor-door report goes to a counselor and must carry
        # nothing the candidate's account knows (decision 24).
        _merge_profile(inputs, user_id)

    draft = _draft_for(data, user_id)
    promote = draft is not None and not plan.always_new_row
    target_id = draft.id if promote else str(uuid4())
    token = new_access_token() if plan.gives_token else None
    # Plain values from here on: redeem() commits, and may roll back, and both
    # expire every row this request has loaded.
    stage = partial(
        _stage_run, plan,
        user_id=user_id,
        inputs=inputs,
        target_id=target_id,
        promote=promote,
        draft_id=draft.id if draft is not None else None,
        token=token,
        counselor_id=code.owner_id if plan.door == doors.ADVISOR else None,
    )
    held_draft_used = user_id is None and draft is not None

    stage()
    if code is None:
        db.session.commit()
    else:
        refused = code_service.redeem(
            code,
            # Promo: the account, for once-per-account. Advisor: nobody — the
            # candidate stays out of the counselor's records but for prénom/nom.
            user_id=user_id if plan.door == doors.PROMO else None,
            target_type="analysis",
            target_id=target_id,
        )
        if refused:
            # redeem() rolls back on a key violation but not on its early
            # EXHAUSTED: either way the staged row must not outlive the refusal.
            db.session.rollback()
            return jsonify({"error": refused}), 409
        if not _is_queued_at(target_id, plan.door):
            # Another request took the slot first: redeem() rolled back — the
            # row with it — and committed only the redemption on its retry.
            # The use is spent, so put the row back and commit it.
            stage()
            db.session.commit()

    # Hand the slow Anthropic call to a background thread so the HTTP
    # response returns immediately; the page polls for status.
    start_analysis(target_id, current_app._get_current_object())

    if plan.door == doors.ADVISOR:
        body = {}
    else:
        body = {"analysis": db.session.get(Analysis, target_id).to_dict()}
        if token:
            body["access_token"] = token
    response = jsonify(body)
    if held_draft_used:
        # The row it held now carries a fresh key, or is gone.
        held.clear_cookie(response)
    return response, 201


@analyses_bp.post("/draft")
def save_draft():
    """Create or update a draft.

    Signed in: the account's own draft, as before. Signed out: the draft this
    browser holds (four-doors spec, decision 34) — saved by the doors that need
    a sign-in round trip, keyed by the neoori_hold cookie and never by
    anything in the body.

    What is stored is the allow-list in analysis_inputs.clean (decision 37),
    for both callers: it replaces the old per-key pops and the _path stamp,
    since a key that is not allowed is never kept.
    """
    user_id = _optional_user_id()
    data = json_object()
    # dict_field, not a bare data.get(): a non-dict "inputs" would be stored
    # as-is on the model, then crash Analysis.parcours -- called from
    # to_dict() a few lines below -- via (self.inputs or {}).get("_path").
    inputs, errors = analysis_inputs.clean(dict_field(data, "inputs"))
    if errors:
        return jsonify({"errors": errors}), 400

    if user_id is None:
        row, token, status = held.held_row(draft_only=True), None, 200
        if row is None:
            if held.too_many():
                return jsonify({"error": held.TOO_MANY}), 429
            row, token = held.new_held_draft(inputs)
            status = 201
        else:
            row.inputs = inputs
        db.session.commit()
        # "held" tells the form this draft belongs to the browser, not to an
        # account (it goes at logout). A signed-in save never carries the key.
        response = jsonify({"analysis": row.to_dict(), "held": True})
        if token:
            held.set_cookie(response, token)
        return response, status

    # text_field, not a bare data.get(): a non-string draft_id (a list, a
    # dict) reaching filter_by(id=draft_id) as a query parameter raises
    # sqlalchemy.exc.ProgrammingError ("type 'list' is not supported") --
    # no id is ever actually a list, so falling back to "no draft_id" (a new
    # draft) is the right answer, same as an absent one.
    draft_id = text_field(data, "draft_id")
    if draft_id:
        analysis = Analysis.query.filter_by(id=draft_id, user_id=user_id, status="draft").first()
        if analysis:
            analysis.inputs = inputs
            db.session.commit()
            return jsonify({"analysis": analysis.to_dict()}), 200

    analysis = Analysis(user_id=user_id, inputs=inputs, status="draft")
    db.session.add(analysis)
    db.session.commit()
    return jsonify({"analysis": analysis.to_dict()}), 201


@analyses_bp.get("/held")
def get_held():
    """The draft this browser holds, to refill the form after a round trip."""
    row = held.held_row(draft_only=True)
    if row is None:
        return jsonify({"error": "Votre brouillon a expiré."}), 404
    return jsonify({"analysis": row.to_dict()}), 200


@analyses_bp.post("/hold")
def hold_report():
    """« Créer un compte pour le garder » (decision 32): hand a no-login report
    to the cookie, so the claim after sign-in finds it. The page proves it
    holds the link with the header."""
    raw = request.headers.get(TOKEN_HEADER, "")
    row = Analysis.query.filter_by(access_token_hash=hash_token(raw)).first() if raw else None
    if row is None or row.user_id is not None or row.door != doors.ANONYMOUS:
        return jsonify({"error": "Ce lien n'est plus valide."}), 404
    response = jsonify({})
    held.set_cookie(response, raw)
    return response, 200


@analyses_bp.post("/claim")
def claim():
    """Attach the held row to the signed-in account, then forget the cookie."""
    user_id = _optional_user_id()
    if user_id is None:
        return jsonify({"error": doors.SIGN_IN}), 401
    row = held.held_row()
    if row is None:
        return jsonify({"error": "Votre brouillon a expiré."}), 404
    held.attach(row, user_id)
    db.session.commit()
    response = jsonify({"analysis": row.to_dict()})
    held.clear_cookie(response)
    return response, 200


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
    /held, by its cookie: its key never leaves the cookie. _may_access has the
    last word, so an advisor-door report is refused here too, whatever it holds."""
    presented = _header_token_hash()
    row = Analysis.query.filter_by(access_token_hash=presented).first() if presented else None
    if row is None or row.status == "draft" or not _may_access(row):
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


@analyses_bp.post("/<analysis_id>/relaunch")
@jwt_required()
def relaunch_promo(analysis_id):
    """A failed promo-door run, relaunched by its owner on the same row with no
    new code use (four-doors spec, decision 49). The use was spent before the
    run, once-per-account would refuse a second try, and unlock_service.refusal
    refuses an errored row: without this, a failure burns the code.

    A conditional update, so a double click starts one run, not two.
    """
    analysis = Analysis.query.get_or_404(analysis_id)
    if analysis.user_id is None or analysis.user_id != get_jwt_identity() or analysis.door != doors.PROMO:
        return jsonify({"error": "Accès non autorisé."}), 403
    claimed = (
        Analysis.query
        .filter(Analysis.id == analysis.id, Analysis.status.in_(("error", "timeout")))
        .update({"status": "queued", "progress": 0}, synchronize_session=False)
    )
    db.session.commit()
    if claimed != 1:
        return jsonify({"error": "Cette analyse n'a pas besoin d'être relancée."}), 409
    start_analysis(analysis.id, current_app._get_current_object())
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

def _draft_for(data: dict, user_id: str | None) -> Analysis | None:
    """The draft this submit replaces: the caller's own (draft_id) when signed
    in, the one this browser holds when not. None when there is none."""
    if user_id is not None:
        draft_id = text_field(data, "draft_id")
        if not draft_id:
            return None
        return Analysis.query.filter_by(id=draft_id, user_id=user_id, status="draft").first()
    return held.held_row(draft_only=True)


def _stage_run(
    plan: doors.Plan,
    *,
    user_id: str | None,
    inputs: dict,
    target_id: str,
    promote: bool,
    draft_id: str | None,
    token: str | None,
    counselor_id: str | None,
) -> None:
    """Put one submitted run in the session — its row and its run_log entry —
    for the caller to commit.

    The row is the caller's draft promoted in place (`promote`), else a new row
    that replaces the draft, if there was one: a draft the person holds an id
    to is never reused where the report is not theirs. Everything arrives as
    ids and plain values, and the draft is looked up again here, because this
    can run a second time after redeem() rolled the first attempt back.
    """
    analysis = db.session.get(Analysis, target_id) if promote else None
    if analysis is None:
        analysis = Analysis(id=target_id)
        db.session.add(analysis)
    if draft_id is not None and not promote:
        replaced = db.session.get(Analysis, draft_id)
        if replaced is not None:
            db.session.delete(replaced)

    now = datetime.utcnow()
    analysis.inputs = inputs
    analysis.status = "queued"
    # The run's time, not the draft's: retention and the report's date count
    # from here (decision 34).
    analysis.created_at = now
    analysis.door = plan.door
    analysis.user_id = user_id if plan.needs_session else None
    analysis.counselor_id = counselor_id
    analysis.pending_user_id = None
    analysis.access_token_hash = hash_token(token) if token else None
    if plan.needs_consent:
        analysis.consent_at = now
        analysis.consent_version = CONSENT_VERSION
    # Stored on the row as well as in the inputs blob: which voyage fed this
    # analysis stays queryable -- B2G traceability, as with prompt_version_id.
    analysis.voyage_id = inputs.get("_voyage_id")
    doors.log_run(plan.door, user_id)


def _is_queued_at(analysis_id: str, door: str) -> bool:
    """Whether the run's row is committed, queued, through this door."""
    row = db.session.get(Analysis, analysis_id)
    return row is not None and row.status == "queued" and row.door == door


def _merge_profile(inputs: dict, user_id: str | None) -> None:
    """Copy the Profil de base and le voyage into this analysis's inputs.

    The ordinary profile fields are copied so the analysis stays readable on
    its own (a later profile edit must not silently rewrite an already-
    delivered report). Bloc 5 is reduced to prompt_context() first, and the
    OETH flag becomes a plain boolean — neither the raw condition answers nor
    the status itself is ever stored on the analysis.

    The voyage fold runs whether or not a profile exists. The submit calls
    this for the account and promo doors only (doors.Plan.folds_profile), both
    of which need a session, so user_id is always set there; the falsy branch
    is kept so nothing here depends on that.
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

    The first two statements are defence in depth. The client's keys are
    already an allow-list (analysis_inputs.clean), so a posted _voyage or
    _voyage_id never gets here. They stay because both are server-only and a
    key that slipped through would do real harm: a posted _voyage reaches the
    model under the real "CE QUE LE VOYAGE A REVELE" header (prompt injection,
    and a framework-vocabulary leak past every guard prompt_context()
    enforces), and a posted _voyage_id either stamps another user's voyage
    onto this row's traceability column or, if it names no row, raises an
    uncaught IntegrityError on the commit that writes it — a 500 any
    signed-in account could trigger.
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
