from uuid import uuid4
from datetime import datetime
from ..extensions import db


# pending  — submitted, not yet reviewed
# approved — user.role is 'counselor' for exactly this status
# rejected — the demande failed review, terminal
# revoked  — was approved, access withdrawn afterwards. Kept apart from
#            'rejected' because they are not the same fact: different message
#            on screen, different line in any report.
STATUSES = ("pending", "approved", "rejected", "revoked")

# The structure types the demande form offers, in the PM's order. Stored as a
# slug so the label can be reworded without a migration; the French labels live
# in the frontend beside the select.
TYPES_STRUCTURE = (
    "cap_emploi",             # Cap Emploi / OPS
    "mission_locale",
    "france_travail",
    "association",
    "esat_ea",                # ESAT / Entreprise adaptée
    "formation_cfa",          # Organisme de formation / CFA
    "etablissement_scolaire", # lycée, université, CIO
    "collectivite",           # mairie, département, région, CCAS, MDPH
    "medico_social",
    "entreprise_rh",          # entreprise / cabinet RH, recrutement, intérim
    "organisation_pro",       # organisation professionnelle / OPCO / syndicat
    "independant",            # indépendant / auto-entrepreneur / consultant
    "autre",
)

# The one type whose SIRET is optional: a consultant may not have registered
# one yet. Declared here rather than inline so the route and any later caller
# read the same rule.
TYPE_SIRET_OPTIONAL = "independant"

DOMAINES = (
    "insertion_emploi",
    "handicap",
    "orientation_bilan",
    "formation",
    "recrutement_entreprises",
    "accompagnement_social",
    "education",
    "autre",
)


class CounselorProfile(db.Model):
    """One demande per account. Nothing counselor-shaped lives on `users`:
    to_dict() there is returned on every /auth/me, to every candidate."""

    __tablename__ = "counselor_profiles"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id = db.Column(
        db.String(36), db.ForeignKey("users.id"), unique=True, nullable=False, index=True
    )

    structure = db.Column(db.String(255), nullable=False)
    fonction = db.Column(db.String(255), nullable=False)
    telephone = db.Column(db.String(32), nullable=False)

    # Added with the PM's 2026-09-30 form. All nullable because the demandes
    # already in production carry none of them; the route requires them of new
    # submissions instead, so the schema stays kind to rows that predate it.
    nom_complet = db.Column(db.String(255), nullable=True)
    type_structure = db.Column(db.String(64), nullable=True)
    type_structure_autre = db.Column(db.String(255), nullable=True)
    siret = db.Column(db.String(14), nullable=True)
    adresse_rue = db.Column(db.String(255), nullable=True)
    adresse_code_postal = db.Column(db.String(16), nullable=True)
    adresse_ville = db.Column(db.String(128), nullable=True)
    domaines = db.Column(db.JSON, nullable=True)

    # Retired, not dropped — the same discipline as profiles.rayon. Nothing
    # asks for either any more (the PM merged email_pro into the account email
    # and removed « Précisions »), but rows written while they were asked keep
    # their answers and the admin panel still prints them.
    email_pro = db.Column(db.String(255), nullable=True)
    message = db.Column(db.Text, nullable=True)

    status = db.Column(
        db.Enum(*STATUSES, name="counselor_status"),
        nullable=False,
        default="pending",
        index=True,
    )

    # Both NULL = illimité. The admin's two dials: how many codes, and how many
    # uses any one of them may carry. An account-wide redemption quota would be
    # meaningless once a code is multi-use — spec decision 4.
    max_codes = db.Column(db.Integer, nullable=True)
    max_uses_per_code = db.Column(db.Integer, nullable=True)

    decision_reason = db.Column(db.Text, nullable=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    reviewed_by_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # Two FKs to the same table, so both relationships must name their column.
    user = db.relationship(
        "User",
        foreign_keys=[user_id],
        backref=db.backref("counselor_profile", uselist=False),
    )
    reviewed_by = db.relationship("User", foreign_keys=[reviewed_by_id])

    def to_dict(self, *, with_user: bool = False) -> dict:
        data = {
            "id": self.id,
            "user_id": self.user_id,
            "structure": self.structure,
            "fonction": self.fonction,
            "telephone": self.telephone,
            "nom_complet": self.nom_complet,
            "type_structure": self.type_structure,
            "type_structure_autre": self.type_structure_autre,
            "siret": self.siret,
            "adresse_rue": self.adresse_rue,
            "adresse_code_postal": self.adresse_code_postal,
            "adresse_ville": self.adresse_ville,
            "domaines": self.domaines or [],
            "email_pro": self.email_pro,
            "message": self.message,
            "status": self.status,
            "max_codes": self.max_codes,
            "max_uses_per_code": self.max_uses_per_code,
            "decision_reason": self.decision_reason,
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
            "created_at": self.created_at.isoformat(),
        }
        if with_user:
            data["user"] = self.user.to_dict()
        return data
