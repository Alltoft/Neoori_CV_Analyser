from uuid import uuid4
from datetime import datetime, timedelta

from flask import current_app

from ..extensions import db
from ..services import section_registry as registry


class Analysis(db.Model):
    __tablename__ = "analyses"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=True, index=True)
    prompt_version_id = db.Column(db.String(36), db.ForeignKey("prompt_versions.id"), nullable=True)
    # Which voyage fed this analysis, when the person has played one. Nullable
    # and never required: an analysis runs identically with no voyage.
    # ondelete="SET NULL": erasing a voyage (DELETE /api/voyage, RGPD) must not
    # delete the analyses it fed -- those are the person's own reports and
    # their B2G traceability rows -- but the link must not dangle either.
    voyage_id = db.Column(
        db.String(36), db.ForeignKey("voyages.id", ondelete="SET NULL"), nullable=True, index=True
    )

    status = db.Column(
        db.Enum("draft", "queued", "running", "success", "error", "timeout", name="analysis_status"),
        nullable=False,
        default="draft",
        index=True,
    )

    # The 8 input fields stored as JSON
    inputs = db.Column(db.JSON, nullable=True)

    # Parsed AI output — dict keyed by section key ('1'..'11', 'verdict'),
    # each a section object. See services/section_registry.py.
    output = db.Column(db.JSON, nullable=True)

    # Raw text response from Claude, preserved for traceability
    raw_output = db.Column(db.Text, nullable=True)

    tokens_in = db.Column(db.Integer, nullable=True)
    tokens_out = db.Column(db.Integer, nullable=True)

    # How far the generation has got, 0-99 while running and 100 once the row
    # is 'success'. Written from the stream itself (see anthropic_service) so
    # the waiting screen reports the run instead of animating a clock.
    progress = db.Column(db.SmallInteger, nullable=False, default=0, server_default="0")

    # The retired /c/<share_token> link (four-doors spec, decision 43): kept,
    # no longer minted.
    share_token = db.Column(db.String(64), unique=True, nullable=True, index=True)

    # Paywall unlock traceability: 'code' (counselor) or 'payment' (Stripe)
    unlock_method = db.Column(db.String(16), nullable=True)
    unlocked_at = db.Column(db.DateTime, nullable=True)
    stripe_session_id = db.Column(db.String(255), nullable=True, index=True)

    # Which of the four doors this run came through (four-doors spec): account
    # / promo / advisor / anonymous, set at submit. 'legacy' marks the ownerless
    # rows written before accounts were required (decision 44). NULL for drafts
    # and for owned rows that predate the doors.
    door = db.Column(db.String(16), nullable=True)
    # SHA-256 of the key to a no-login report or a held draft (decisions 30,
    # 34). The key itself is never stored.
    access_token_hash = db.Column(db.CHAR(64), unique=True, nullable=True)
    # The counselor an advisor-door report belongs to — and the only person who
    # may read it (ruling 2). SET NULL keeps the row closed: `door` still says
    # advisor, and _may_access refuses on either.
    counselor_id = db.Column(
        db.String(36), db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # The account a held row waits for: set by password signup, attached at
    # verify-email, dropped if the address is proven any other way first
    # (decisions 34, 36).
    pending_user_id = db.Column(
        db.String(36), db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # The CGV + privacy box at the advisor and anonymous doors (decisions 25,
    # 31), which have no signup consent to rely on.
    consent_at = db.Column(db.DateTime, nullable=True)
    consent_version = db.Column(db.String(16), nullable=True)
    # When the row last went 'running' — the stale-run reaper's clock
    # (decision 47). created_at is wrong for a relaunch or an unlock.
    started_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)

    counselor_notes = db.relationship("CounselorNote", backref="analysis", lazy="dynamic")

    __table_args__ = (db.Index("ix_analyses_door_created_at", "door", "created_at"),)

    @property
    def parcours(self) -> str:
        """Registry id for this analysis. Legacy 'A' rows and retired ids read as parcours 1."""
        return registry.normalize((self.inputs or {}).get("_path"))

    def _access_expires_at(self) -> str | None:
        """When an unclaimed no-login report's link stops working (four-doors
        spec, decision 32). None for every other row."""
        if self.door != "anonymous" or self.user_id is not None or self.created_at is None:
            return None
        days = current_app.config.get("ANONYMOUS_RETENTION_DAYS", 30)
        return (self.created_at + timedelta(days=days)).isoformat()

    def to_dict(self):
        parcours = self.parcours
        data = {
            "id": self.id,
            "status": self.status,
            "inputs": self.inputs,
            "tokens_in": self.tokens_in,
            "tokens_out": self.tokens_out,
            "progress": 100 if self.status == "success" else (self.progress or 0),
            "prompt_version_id": self.prompt_version_id,
            "voyage_id": self.voyage_id,
            "unlock_method": self.unlock_method,
            "unlocked_at": self.unlocked_at.isoformat() if self.unlocked_at else None,
            "door": self.door,
            "access_expires_at": self._access_expires_at(),
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }

        # Render instructions for the client: ordered, with titles and render
        # mode. The client must never sort output keys itself — "verdict" sits
        # between "3" and "4", and a string sort puts "10" before "2".
        data["sections_meta"] = registry.sections_meta(parcours)
        if self.output:
            data["output"] = self.output
        return data
