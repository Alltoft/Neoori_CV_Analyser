"""One redemption path, shared by the two call sites that redeem a code.

POST /api/analyses/<id>/unlock and POST /api/voyage/unlock each did their own
lookup and their own `uses_count += 1`. They now agree on three refusals —
inactive, expired, exhausted — and on writing the row that says who redeemed
what, when.
"""
import re
from datetime import datetime

from ..extensions import db
from ..models.code_redemption import CodeRedemption
from ..models.counselor_code import CounselorCode

INVALID = "Code invalide ou désactivé."
EXPIRED = "Ce code a expiré."
EXHAUSTED = "Ce code a atteint sa limite d'utilisation."


def normalize(raw) -> str:
    """Accept "ABCD1234", "abcd 1234", "ABCD-1234"… — codes are 8 alnum chars.

    A non-string value yields "", so the route answers its own « Code requis. »
    instead of raising AttributeError on .strip() -> an unhandled 500.
    """
    return re.sub(r"[^A-Za-z0-9]", "", raw if isinstance(raw, str) else "").upper()


def redemption_count(code_id: str) -> int:
    return CodeRedemption.query.filter_by(code_id=code_id).count()


def resolve(code_str: str) -> tuple[CounselorCode | None, str | None]:
    """The code, or the French refusal to hand back verbatim.

    Counted, not read off uses_count: that column is an increment which can
    drift, and rows that predate this feature carry one with no redemption
    behind it. Their max_uses is NULL, so the check below never reaches them.

    with_for_update locks the row for the rest of the transaction on MySQL, so
    two simultaneous redemptions of a code's last use cannot both pass. SQLite
    (tests) omits the clause; the check itself still runs.
    """
    code = CounselorCode.query.filter_by(code=code_str).with_for_update().first()
    if code is None or not code.is_active or code.revoked_at is not None:
        return None, INVALID
    if code.expires_at is not None and code.expires_at <= datetime.utcnow():
        return None, EXPIRED
    if code.max_uses is not None and redemption_count(code.id) >= code.max_uses:
        return None, EXHAUSTED
    return code, None


def record(code: CounselorCode, *, user_id: str | None, target_type: str, target_id: str) -> None:
    """Log the redemption and bump the legacy counter.

    Deliberately does not commit: the caller owns the transaction this belongs
    to, and the unlock it accompanies must land or not land with it.
    """
    db.session.add(CodeRedemption(
        code_id=code.id,
        user_id=user_id,
        target_type=target_type,
        target_id=target_id,
    ))
    code.uses_count += 1
