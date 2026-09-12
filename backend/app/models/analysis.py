from uuid import uuid4
from datetime import datetime
from ..extensions import db
from ..services import section_registry as registry


# GET /api/c/<share_token> is public and unauthenticated -- anyone holding
# the link gets whatever to_dict(audience="counselor") puts in "inputs".
# This allow-list mirrors every `analysis.inputs.X` access in
# frontend/src/app/c/[token]/page.tsx (verified 2026-09-12): the parcours
# discriminator, the candidate name shown in the header, and the "key facts"
# strip for both the parcours-1/2 layout and the parcours-3 layout. Anything
# that page does not render -- cv_text, the encrypted-profile-derived
# _conditions/_oeth lines, the _voyage/_voyage_id lines -- must never travel
# over this public link. Add a key here only after confirming that page
# reads it; this must stay an allow-list, never a deny-list, so an
# unclassified future field defaults to hidden.
COUNSELOR_VISIBLE_INPUT_KEYS = frozenset({
    "_path",
    "prenom",
    "nom",
    "cible_visee",
    "type_mobilite",
    "situation_actuelle",
    "notes_specifiques",
    "_sub_profile",
    "aime",
    "refuse",
    "accompagnement",
})


class Analysis(db.Model):
    __tablename__ = "analyses"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=True, index=True)
    prompt_version_id = db.Column(db.String(36), db.ForeignKey("prompt_versions.id"), nullable=True)
    # Which voyage fed this analysis, when the person has played one. Nullable
    # and never required: every parcours runs identically with no voyage.
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

    # Parsed AI output — dict keyed by section key, each a section object.
    # Keys depend on the parcours: '1'..'11' (P1), 'A'..'G' (P2), 'I'..'VI' (P3).
    # See services/section_registry.py.
    output = db.Column(db.JSON, nullable=True)

    # Raw text response from Claude, preserved for traceability
    raw_output = db.Column(db.Text, nullable=True)

    tokens_in = db.Column(db.Integer, nullable=True)
    tokens_out = db.Column(db.Integer, nullable=True)

    # How far the generation has got, 0-99 while running and 100 once the row
    # is 'success'. Written from the stream itself (see anthropic_service) so
    # the waiting screen reports the run instead of animating a clock.
    progress = db.Column(db.SmallInteger, nullable=False, default=0, server_default="0")

    # Public token for counselor share link: /c/<share_token>
    share_token = db.Column(db.String(64), unique=True, nullable=True, index=True)

    # Paywall unlock traceability: 'code' (counselor) or 'payment' (Stripe)
    unlock_method = db.Column(db.String(16), nullable=True)
    unlocked_at = db.Column(db.DateTime, nullable=True)
    stripe_session_id = db.Column(db.String(255), nullable=True, index=True)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)

    counselor_notes = db.relationship("CounselorNote", backref="analysis", lazy="dynamic")

    @property
    def parcours(self) -> str:
        """Registry id for this analysis, tolerant of legacy 'A'/'B' rows."""
        return registry.normalize((self.inputs or {}).get("_path"))

    def to_dict(self, audience: str = "candidate"):
        parcours = self.parcours
        data = {
            "id": self.id,
            "status": self.status,
            "inputs": self.inputs,
            "tokens_in": self.tokens_in,
            "tokens_out": self.tokens_out,
            "progress": 100 if self.status == "success" else (self.progress or 0),
            "share_token": self.share_token,
            "prompt_version_id": self.prompt_version_id,
            "voyage_id": self.voyage_id,
            "unlock_method": self.unlock_method,
            "unlocked_at": self.unlocked_at.isoformat() if self.unlocked_at else None,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }

        # Render instructions for the client: ordered, with titles and render
        # mode. The client must never sort output keys itself — letter and
        # Roman keys don't sort numerically or lexicographically.
        meta = registry.sections_meta(parcours)
        counselor = list(registry.counselor_keys(parcours))
        if audience == "counselor":
            # Spec rule: same analysis object, different view — no regeneration.
            meta = [m for m in meta if m["key"] in set(counselor)]
            # Public share link: ship only what the counselor page renders,
            # never the candidate's full submission. See
            # COUNSELOR_VISIBLE_INPUT_KEYS above -- the candidate audience
            # (default) is untouched and keeps every input key.
            data["inputs"] = {
                k: v for k, v in (self.inputs or {}).items()
                if k in COUNSELOR_VISIBLE_INPUT_KEYS
            }
        data["sections_meta"] = meta
        # Lets the candidate view render its "vue conseiller" tab without a
        # second request, and without keeping its own copy of this rule.
        data["counselor_keys"] = counselor

        if self.output:
            if audience == "counselor":
                keep = set(registry.counselor_keys(parcours))
                data["output"] = {k: v for k, v in self.output.items() if k in keep}
            else:
                data["output"] = self.output

        return data
