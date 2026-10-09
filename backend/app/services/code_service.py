"""One redemption path for every code (four-doors spec, decisions 17-23).

A code's kind is derived: no owner means admin-minted, a promo code; an owner
means a conseiller code. Uses are counted per kind — a single-use conseiller
code opens one analysis AND one voyage (ruling 10) — and the ceiling is the
database's to enforce, not a count's: see redeem().
"""
import re
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.exc import IntegrityError

from ..extensions import db
from ..models.code_redemption import CodeRedemption
from ..models.counselor_code import CounselorCode
from ..models.counselor_profile import CounselorProfile

INVALID = "Code invalide ou désactivé."
EXPIRED = "Ce code a expiré."
EXHAUSTED = "Ce code a atteint sa limite d'utilisation."
ALREADY_USED = "Vous avez déjà utilisé ce code."
REQUIRED = "Code requis."
NOT_FOR_UNLOCK = (
    "Ce code est un code conseiller : avec lui, le rapport complet est envoyé à "
    "votre conseiller. Lancez une nouvelle analyse et choisissez « J'ai un code "
    "conseiller »."
)

PROMO = "promo"
CONSEILLER = "conseiller"

# The door (services/doors.py names) each kind of code belongs to, and what to
# say to someone who typed it at the other one.
DOOR_OF = {PROMO: "promo", CONSEILLER: "advisor"}
WRONG_DOOR = {
    PROMO: "Ce code est un code promo : choisissez « J'ai un code promo ».",
    CONSEILLER: "Ce code est un code conseiller : choisissez « J'ai un code conseiller ».",
}


@dataclass(frozen=True)
class DoorRefusal:
    message: str
    status: int
    # The door this code belongs to, when it was typed at the wrong one: the
    # panel switches to it (spec decision 21).
    door: str | None = None


def normalize(raw) -> str:
    """Accept "ABCD1234", "abcd 1234", "ABCD-1234"… — codes are 8 alnum chars.

    A non-string value yields "", so the route answers its own « Code requis. »
    instead of raising AttributeError on .strip() -> an unhandled 500.
    """
    return re.sub(r"[^A-Za-z0-9]", "", raw if isinstance(raw, str) else "").upper()


def kind(code: CounselorCode) -> str:
    return PROMO if code.owner_id is None else CONSEILLER


def redemption_count(code_id: str, target_type: str | None = None) -> int:
    query = CodeRedemption.query.filter_by(code_id=code_id)
    if target_type is not None:
        query = query.filter_by(target_type=target_type)
    return query.count()


def _owner_approved(code: CounselorCode) -> bool:
    """A conseiller code works only while its counselor is approved (spec
    decision 20). A promo code has no counselor to ask."""
    if code.owner_id is None:
        return True
    profile = CounselorProfile.query.filter_by(user_id=code.owner_id).first()
    return profile is not None and profile.status == "approved"


def _used_by(code_id: str, target_type: str, user_id: str) -> bool:
    return CodeRedemption.query.filter_by(
        code_id=code_id, target_type=target_type, user_id=user_id
    ).first() is not None


def resolve(code_str: str, target_type: str) -> tuple[CounselorCode | None, str | None]:
    """The code, or the French refusal to hand back verbatim.

    Counted per kind from code_redemptions, never off uses_count (a legacy
    increment that can drift). This count is advisory: it gives the early,
    friendly answer. The guarantee is redeem()'s slot key.
    """
    code = CounselorCode.query.filter_by(code=code_str).with_for_update().first()
    if code is None or not code.is_active or code.revoked_at is not None:
        return None, INVALID
    if not _owner_approved(code):
        return None, INVALID
    if code.expires_at is not None and code.expires_at <= datetime.utcnow():
        return None, EXPIRED
    if code.max_uses is not None and redemption_count(code.id, target_type) >= code.max_uses:
        return None, EXHAUSTED
    return code, None


def resolve_for_door(raw, door: str, user_id: str | None) -> tuple[CounselorCode | None, DoorRefusal | None]:
    """The code a door may spend, or why not — including « wrong door »."""
    code_str = normalize(raw)
    if not code_str:
        return None, DoorRefusal(REQUIRED, 400)
    code, refusal = resolve(code_str, "analysis")
    if refusal:
        return None, DoorRefusal(refusal, 400)
    code_kind = kind(code)
    if DOOR_OF[code_kind] != door:
        return None, DoorRefusal(WRONG_DOOR[code_kind], 409, DOOR_OF[code_kind])
    if code_kind == PROMO and user_id is not None and _used_by(code.id, "analysis", user_id):
        return None, DoorRefusal(ALREADY_USED, 409)
    return code, None


def redeem(code: CounselorCode, *, user_id: str | None, target_type: str, target_id: str) -> str | None:
    """Write the redemption and COMMIT it — before whatever it pays for starts.

    For a limited code the row takes `slot = used + 1`, and the unique key on
    (code_id, target_type, slot) refuses a second request that read the same
    count. That read can be stale: under MySQL's REPEATABLE READ the snapshot is
    fixed at the transaction's first read. On a violation the transaction is
    rolled back — the next one gets a fresh snapshot — and the count is read
    again once. Unlimited codes write slot NULL, which never collides.

    Returns None on success, or the French refusal: EXHAUSTED, or ALREADY_USED
    when this account already spent this code on this kind (the unique key on
    (code_id, target_type, user_id)). A row already recorded for this very
    target — a retried request — counts as success.
    """
    code_id, max_uses = code.id, code.max_uses
    for _attempt in range(2):
        used = redemption_count(code_id, target_type)
        if max_uses is not None and used >= max_uses:
            return EXHAUSTED
        try:
            db.session.add(CodeRedemption(
                code_id=code_id,
                user_id=user_id,
                target_type=target_type,
                target_id=target_id,
                slot=used + 1 if max_uses is not None else None,
            ))
            # Flushed here, inside the try: the update below would autoflush
            # it anyway, and a unique-key violation must land in the except,
            # not escape as a 500.
            db.session.flush()
            # The legacy counter, kept for the admin screens that still read it.
            CounselorCode.query.filter_by(id=code_id).update(
                {"uses_count": CounselorCode.uses_count + 1}, synchronize_session=False
            )
            db.session.commit()
            return None
        except IntegrityError:
            db.session.rollback()
            if user_id is not None and _used_by(code_id, target_type, user_id):
                return ALREADY_USED
            if CodeRedemption.query.filter_by(
                code_id=code_id, target_type=target_type, target_id=target_id
            ).first() is not None:
                return None
    return EXHAUSTED


def use_counts_by_kind(code_ids: list[str]) -> dict[str, dict[str, int]]:
    """{code_id: {"analysis": n, "voyage": m}} in one grouped query — the
    counselor's and the admin's code tables both show uses per kind (ruling 10)."""
    if not code_ids:
        return {}
    rows = (
        db.session.query(CodeRedemption.code_id, CodeRedemption.target_type, db.func.count(CodeRedemption.id))
        .filter(CodeRedemption.code_id.in_(code_ids))
        .group_by(CodeRedemption.code_id, CodeRedemption.target_type)
        .all()
    )
    counts: dict[str, dict[str, int]] = {}
    for code_id, target_type, n in rows:
        counts.setdefault(code_id, {"analysis": 0, "voyage": 0})[target_type] = n
    return counts
