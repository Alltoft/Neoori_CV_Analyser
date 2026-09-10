"""Le voyage — the six-session exploration and the counselor's private notes.

Two models, one file, because they share one lifecycle:

  Voyage      one attempt at the six sessions. Many rows per user — a retake is
              a new row and the old one is kept, because analyses reference it
              — with at most one *open* at a time; POST /api/voyage enforces
              that, not the schema.
  VoyageNote  one counselor's private note on one voyage. Plaintext on purpose:
              it is the counselor's own writing about their own practice, not
              the person's answers.

Encryption follows SensitiveProfile (models/profile.py) exactly: the columns
hold Fernet tokens and are useless to anything that dumps rows, the payload is
reached through properties and decrypted in-process only, and to_dict() never
carries it. A psychometric read-out — what someone fears, what they would
sacrifice — is more sensitive than bloc 5, not less.

Of all of it, one derived thing may reach the candidate: micro_phrase. Never a
score, never an axis, never a trait or a framework name (spec decision 7).
"""
from datetime import datetime
from uuid import uuid4

from ..extensions import db
from ..services.voyage import bank, scoring
from ..utils import crypto

# Stamped on the row at creation, so a consent text change is traceable.
CONSENT_VERSION = "voyage-v1"

STATUS_EN_COURS, STATUS_S0, STATUS_TERMINE = "en_cours", "s0_termine", "termine"
STATUSES = (STATUS_EN_COURS, STATUS_S0, STATUS_TERMINE)
OPEN_STATUSES = (STATUS_EN_COURS, STATUS_S0)

MICRO_STATUSES = ("none", "generating", "success", "error")
PORTRAIT_STATUSES = ("none", "generating", "draft", "validated", "error")

# The counselor manual's page-20 template, in order.
PORTRAIT_KEYS = ("accroche", "qui_tu_es", "vibrer", "besoins", "chemins", "pas_encore")

# The three lock reasons, in French: the API returns them as `error` and the
# hub renders them on the locked card. frontend/src/types/voyage.ts mirrors
# them byte for byte.
LOCK_CODE = "Avec un conseiller"
LOCK_PROFILE = "Complétez votre profil"
LOCK_ORDER = "Terminez la session précédente"


class Voyage(db.Model):
    """One attempt at the six sessions."""

    __tablename__ = "voyages"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False, index=True)

    # Strings, never a native enum: widening a MySQL ENUM is the one migration
    # step this repo cannot rehearse locally.
    status = db.Column(db.String(16), nullable=False, default=STATUS_EN_COURS, index=True)
    sessions_completed = db.Column(db.JSON, nullable=False, default=list)

    # Psychometric data needs its own consent record — the profile's does not
    # cover it, and the voyage cannot exist without both of these.
    consent_at = db.Column(db.DateTime, nullable=False)
    consent_version = db.Column(db.String(16), nullable=False, default=CONSENT_VERSION)
    age_attested = db.Column(db.Boolean, nullable=False, default=False)

    # Set by POST /api/voyage/unlock. Gates S1-S5.
    counselor_code_id = db.Column(
        db.String(36), db.ForeignKey("counselor_codes.id"), nullable=True
    )

    # Fernet tokens (URL-safe base64), not raw bytes — Text is the right type.
    responses_encrypted = db.Column(db.Text, nullable=True)
    micro_status = db.Column(db.String(16), nullable=False, default="none")
    micro_encrypted = db.Column(db.Text, nullable=True)
    portrait_status = db.Column(db.String(16), nullable=False, default="none")
    portrait_encrypted = db.Column(db.Text, nullable=True)

    portrait_validated_at = db.Column(db.DateTime, nullable=True)
    validated_by_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=True)

    # Set when S5 completes; the link the candidate hands to their counselor.
    share_token = db.Column(db.String(64), unique=True, nullable=True, index=True)

    # Which edition of the bank and the scoring tables produced this row.
    scoring_version = db.Column(db.String(16), nullable=False, default=bank.SCORING_VERSION)

    # Sum of both generation calls, for the cost dashboard.
    tokens_in = db.Column(db.Integer, nullable=True)
    tokens_out = db.Column(db.Integer, nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    completed_at = db.Column(db.DateTime, nullable=True)

    # Two FKs point at users.id, so both relationships must say which one they
    # travel — otherwise the mapper raises AmbiguousForeignKeysError at
    # configuration time (precedent: PromptVersion.author).
    user = db.relationship("User", foreign_keys=[user_id])
    validated_by = db.relationship("User", foreign_keys=[validated_by_id])
    counselor_code = db.relationship("CounselorCode", foreign_keys=[counselor_code_id])
    notes = db.relationship(
        "VoyageNote", backref="voyage", lazy="dynamic", cascade="all, delete-orphan"
    )

    # ── encrypted payloads ───────────────────────────────────────────────────
    @property
    def responses(self) -> dict:
        """{"answers": {item_id: bool | str}, "billets": {session: {field: str}}}.

        Both keys always present, so scoring can read them without a guard.
        A DecryptionError propagates rather than being swallowed: silently
        returning {} would look like "never answered" and lose a session.
        """
        payload = crypto.decrypt_json(self.responses_encrypted) or {}
        return {
            "answers": payload.get("answers") or {},
            "billets": payload.get("billets") or {},
        }

    @responses.setter
    def responses(self, value: dict | None) -> None:
        value = value or {}
        self.responses_encrypted = crypto.encrypt_json({
            "answers": value.get("answers") or {},
            "billets": value.get("billets") or {},
        })

    @property
    def micro(self) -> dict:
        """{"phrase", "prompt_version_id", "tokens_in", "tokens_out", "error"}."""
        return crypto.decrypt_json(self.micro_encrypted) or {}

    @micro.setter
    def micro(self, value: dict | None) -> None:
        self.micro_encrypted = crypto.encrypt_json(value or {})

    @property
    def portrait(self) -> dict:
        """{"sections", "snapshot", "flags", "edited", "prompt_version_id",
        "tokens_in", "tokens_out", "error"}."""
        return crypto.decrypt_json(self.portrait_encrypted) or {}

    @portrait.setter
    def portrait(self, value: dict | None) -> None:
        self.portrait_encrypted = crypto.encrypt_json(value or {})

    # ── derived, candidate-safe ──────────────────────────────────────────────
    @property
    def micro_phrase(self) -> str | None:
        """The one sentence S0 produces — the only derived value a candidate
        may see before a counselor has validated anything."""
        return (self.micro or {}).get("phrase") or None

    @property
    def portrait_sections(self) -> dict[str, str]:
        """The six sections, or {} while any of them is missing."""
        sections = (self.portrait or {}).get("sections") or {}
        if not all(sections.get(key) for key in PORTRAIT_KEYS):
            return {}
        return {key: sections[key] for key in PORTRAIT_KEYS}

    @property
    def is_open(self) -> bool:
        return self.status in OPEN_STATUSES

    @property
    def has_code(self) -> bool:
        # Deliberately permanent: unlock is checked once, at POST
        # /api/voyage/unlock (an inactive code is refused there). This
        # property does not re-check CounselorCode.is_active, so revoking a
        # code later never strands a candidate mid-voyage (contract § C.5).
        return bool(self.counselor_code_id)

    # ── scoring ──────────────────────────────────────────────────────────────
    def synthesis(self) -> dict:
        """The counselor's page-18 sheet, recomputed from the answers.

        Never stored: a corrected scoring table must not leave stale rows
        behind. The portrait keeps its own snapshot for traceability.
        """
        return scoring.synthesize(self.responses)

    # ── lookups ──────────────────────────────────────────────────────────────
    @classmethod
    def open_for(cls, user_id: str) -> "Voyage | None":
        if not user_id:
            return None
        return (
            cls.query
            .filter(cls.user_id == user_id, cls.status.in_(OPEN_STATUSES))
            .order_by(cls.created_at.desc())
            .first()
        )

    @classmethod
    def latest_for(cls, user_id: str) -> "Voyage | None":
        if not user_id:
            return None
        return (
            cls.query.filter_by(user_id=user_id).order_by(cls.created_at.desc()).first()
        )

    @classmethod
    def current_for(cls, user_id: str) -> "Voyage | None":
        """What GET /api/voyage serves: the open one, else the last one played."""
        return cls.open_for(user_id) or cls.latest_for(user_id)

    @classmethod
    def by_token(cls, token: str) -> "Voyage | None":
        if not token:
            return None
        return cls.query.filter_by(share_token=token).first()

    @classmethod
    def for_prompt(cls, user_id: str | None) -> "Voyage | None":
        """The voyage an analysis may quote from.

        A validated portrait first; failing that, a voyage that has produced
        its S0 phrase. A draft portrait is deliberately not enough — before
        restitution, an analysis must not tell the person what the counselor
        has not said to them yet.
        """
        if not user_id:
            return None
        validated = (
            cls.query
            .filter_by(user_id=user_id, portrait_status="validated")
            .order_by(cls.created_at.desc())
            .first()
        )
        if validated is not None:
            return validated
        return (
            cls.query
            .filter_by(user_id=user_id, micro_status="success")
            .order_by(cls.created_at.desc())
            .first()
        )

    # ── serialisation ────────────────────────────────────────────────────────
    def to_dict(self) -> dict:
        """Twelve keys, and no answer, score, portrait text or foreign key
        among them. The sheet and the portrait have their own endpoints with
        their own access rules; anything added here is reachable by the
        candidate on every poll."""
        return {
            "id": self.id,
            "status": self.status,
            "sessions_completed": self.sessions_completed or [],
            "consent_at": self.consent_at.isoformat() if self.consent_at else None,
            "age_attested": bool(self.age_attested),
            # The boolean, never the code or its id.
            "has_code": self.has_code,
            "micro_status": self.micro_status,
            "micro_phrase": self.micro_phrase,
            "portrait_status": self.portrait_status,
            "share_token": self.share_token if self.status == STATUS_TERMINE else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class VoyageNote(db.Model):
    """A counselor's private note on one voyage. Never shown to the candidate."""

    __tablename__ = "voyage_notes"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    voyage_id = db.Column(
        db.String(36),
        db.ForeignKey("voyages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    counselor_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False)
    body = db.Column(db.Text, nullable=True)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    __table_args__ = (
        db.UniqueConstraint("voyage_id", "counselor_id", name="uq_voyage_notes_voyage_counselor"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "voyage_id": self.voyage_id,
            "body": self.body,
            "updated_at": self.updated_at.isoformat(),
        }


def session_lock(voyage: "Voyage | None", profile, n: str) -> str | None:
    """The server-side session gate.

    Returns None when session `n` is open, else the exact French string the API
    returns as `error` and the UI renders on the locked card. `profile` is a
    models.profile.Profile or None; `n` is one of bank.SESSION_IDS — callers
    validate that first.

    Rules, in this order, first failure wins:
      * no voyage                      -> LOCK_ORDER
      * n == "0"                       -> open once the voyage exists
      * n in "1".."5" and no code      -> LOCK_CODE
      * n in "1".."5" and the profile lacks prenom or tranche_age -> LOCK_PROFILE
      * S(n-1) not completed           -> LOCK_ORDER

    The order is the order the person can act in: get a code, then complete the
    profile, then play the session before this one.
    """
    if voyage is None:
        return LOCK_ORDER
    if n == "0":
        return None
    if not voyage.has_code:
        return LOCK_CODE
    prenom = (getattr(profile, "prenom", None) or "").strip()
    tranche_age = (getattr(profile, "tranche_age", None) or "").strip()
    if not prenom or not tranche_age:
        return LOCK_PROFILE
    if str(int(n) - 1) not in (voyage.sessions_completed or []):
        return LOCK_ORDER
    return None
