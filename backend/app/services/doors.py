"""The four doors behind « Générer mon analyse » (four-doors spec).

One table says, per door, which tier runs, who the report is for, what the
door must be given, and which daily cap it counts against. create_analysis
applies it and decides nothing on its own; in particular, nothing the browser
sends chooses a tier any more (decision 14).
"""
from dataclasses import dataclass
from datetime import datetime, timedelta

from flask import current_app

from ..extensions import db
from ..models.run_log import RunLog
from . import tiers

ACCOUNT = "account"
PROMO = "promo"
ADVISOR = "advisor"
ANONYMOUS = "anonymous"
# Not a door: the mark on ownerless rows written before accounts were required.
LEGACY = "legacy"

NAME_MAX = 80

UNKNOWN = "Porte inconnue."
SIGN_IN = "Non authentifié."
SIGNED_IN = "Vous êtes connecté : choisissez « Avec mon compte »."
CONSENT = "Merci d’accepter les CGV et la politique de confidentialité."
IDENTITY = "Prénom et nom requis."
IDENTITY_LONG = "Prénom ou nom trop long (80 caractères maximum)."
ANONYMOUS_CAP = (
    "La version sans compte est très demandée aujourd'hui. Créez un compte, "
    "ou revenez demain."
)
ACCOUNT_CAP = (
    "Vous avez lancé {n} analyses gratuites aujourd'hui. Revenez demain, ou "
    "débloquez une analyse existante."
)


@dataclass(frozen=True)
class Plan:
    door: str
    tier: str
    needs_session: bool      # account, promo: 401 without one
    refuses_session: bool    # anonymous: a signed-in visitor uses « Avec mon compte »
    code_kind: str | None    # code_service.PROMO / CONSEILLER, or no code
    folds_profile: bool      # the Profil de base and le voyage join the inputs
    needs_consent: bool      # no signup consent to rely on
    needs_identity: bool     # prénom + nom, for the counselor (ruling 9)
    always_new_row: bool     # never promote a draft the candidate holds an id to
    gives_token: bool        # the report's only key is a private link
    cap: str | None          # which daily cap counts this run


PLANS = {
    ACCOUNT: Plan(
        door=ACCOUNT, tier=tiers.FREE, needs_session=True, refuses_session=False,
        code_kind=None, folds_profile=True, needs_consent=False, needs_identity=False,
        always_new_row=False, gives_token=False, cap=ACCOUNT,
    ),
    PROMO: Plan(
        door=PROMO, tier=tiers.PAID, needs_session=True, refuses_session=False,
        code_kind="promo", folds_profile=True, needs_consent=False, needs_identity=False,
        always_new_row=False, gives_token=False, cap=None,
    ),
    ADVISOR: Plan(
        door=ADVISOR, tier=tiers.PAID, needs_session=False, refuses_session=False,
        code_kind="conseiller", folds_profile=False, needs_consent=True, needs_identity=True,
        always_new_row=True, gives_token=False, cap=None,
    ),
    ANONYMOUS: Plan(
        door=ANONYMOUS, tier=tiers.FREE, needs_session=False, refuses_session=True,
        code_kind=None, folds_profile=False, needs_consent=True, needs_identity=False,
        always_new_row=False, gives_token=True, cap=ANONYMOUS,
    ),
}


def decide(door, *, user_id: str | None) -> tuple[Plan | None, tuple[str, int] | None]:
    """The plan for this door and this caller, or (message, status)."""
    if door is None and user_id is not None:
        # A form tab older than the doors posts {inputs, tier}: it gets the
        # account door's free tier, never the tier it asked for.
        door = ACCOUNT
    plan = PLANS.get(door) if isinstance(door, str) else None
    if plan is None:
        return None, (UNKNOWN, 400)
    if plan.needs_session and user_id is None:
        return None, (SIGN_IN, 401)
    if plan.refuses_session and user_id is not None:
        return None, (SIGNED_IN, 400)
    return plan, None


def _since() -> datetime:
    return datetime.utcnow() - timedelta(days=1)


def over_cap(plan: Plan, user_id: str | None) -> str | None:
    """The French refusal when this run would pass its daily cap, else None.

    Counted from run_log over the last 24 hours (decision 40), never from
    analyses, which their holders may delete."""
    if plan.cap == ANONYMOUS:
        limit = current_app.config["ANONYMOUS_RUNS_PER_DAY"]
        count = RunLog.query.filter(
            RunLog.door == ANONYMOUS, RunLog.created_at >= _since()
        ).count()
        return ANONYMOUS_CAP if count >= limit else None
    if plan.cap == ACCOUNT:
        limit = current_app.config["FREE_RUNS_PER_ACCOUNT_PER_DAY"]
        count = RunLog.query.filter(
            RunLog.door == ACCOUNT, RunLog.user_id == user_id, RunLog.created_at >= _since()
        ).count()
        return ACCOUNT_CAP.format(n=limit) if count >= limit else None
    return None


def log_run(door: str, user_id: str | None) -> None:
    """Count one submitted run. The caller commits it with the row it counts."""
    db.session.add(RunLog(door=door, user_id=user_id))
