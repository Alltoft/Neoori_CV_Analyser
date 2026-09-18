"""Profil de base — the 6 blocks filled once, reused by every parcours.

Split in two tables on purpose (PM ruling, 2026-07-29):

  Profile           the erasable-under-consent half. Plaintext, returned by
                    the API, safe in logs.
  SensitiveProfile  bloc 5 (work conditions) and the OETH flag. Ciphertext,
                    separate table, never in to_dict(), never in a log, never
                    in a PDF. Decrypted in-process only to build the prompt.

The split is what makes "on ne garde rien" become "vous gardez le contrôle
de ce qu'on garde" defensible to a prescriber: deleting the Profile row is a
complete erasure of the ordinary data, and the sensitive row can be dropped
independently without touching the rest.
"""
from uuid import uuid4
from datetime import datetime

from ..extensions import db
from ..utils import crypto

# Bloc 1 — search radius around the declared city.
SEARCH_RADIUS = ("ma_ville", "30km", "ma_region", "toute_la_france")

# Bloc 2 — replaces the old situation + type_mobilite pair (they were a
# duplicate; the PM merged mobility into situation).
SITUATIONS = (
    "en_recherche",
    "en_reconversion",
    "en_poste_evolution",
    "premiere_insertion",
    "reprise_apres_pause",
)

# Shown only when situation == "en_reconversion".
RECONVERSION_SCOPES = ("meme_domaine", "changer_de_metier", "changer_de_secteur")

# Bloc 1 — brackets, never a date of birth. Routes the Académie des Ori
# variant and gates the youth schemes in parcours 3.
#
# Seven since the voyage brought school-age candidates in: "moins_25" was one
# bucket where the youth schemes need three. The two sets meet at 25 without
# overlapping — 22_24 stops exactly where 25_34 starts — so a 25-year-old has
# one bucket and no row written under the five-bracket set changes meaning.
AGE_BRACKETS = ("14_17", "18_21", "22_24", "25_34", "35_44", "45_54", "55_plus")

# Written before the split and still on rows. Accepted on write so that editing
# any other field does not reject a bracket the person never touched, but never
# offered in a select: the form re-asks. Until they answer, the stored value
# stays usable — voyage.session_lock only requires a non-empty bracket, so the
# re-ask never locks anyone out of S1-S5 mid-journey.
LEGACY_AGE_BRACKETS = ("moins_25",)

ACCEPTED_AGE_BRACKETS = AGE_BRACKETS + LEGACY_AGE_BRACKETS

# « Ton parcours » — asked after session 1, not at the door. The PM's rule is
# that a young person who has just played the childhood scenes is engaged, and
# a short block there is not the entry form they would have closed the tab on.
DIPLOMES = ("sans_diplome", "cap_bep", "bac", "bac_2", "bac_3_plus")

TYPES_ETUDES = ("generales", "technologiques", "professionnelles", "manuelles", "autre")

# The one that filters the pistes: without it nothing can say whether a piste
# is reachable for this person. Names match the spec's output schema.
APPETENCE_ETUDES = ("courtes", "longues", "indecis", "travailler")

# Bloc 5 — the eight families, each rated on three states.
CONDITION_FAMILIES = (
    "rythme",
    "environnement",
    "deplacements",
    "effort_physique",
    "attention",
    "relation",
    "consignes",
    "organisation",
)

CONDITION_STATES = ("me_convient", "possible_avec_adaptation", "a_eviter")


class Profile(db.Model):
    """Blocks 1-4 and the consent record. Plaintext, erasable."""

    __tablename__ = "profiles"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id = db.Column(
        db.String(36), db.ForeignKey("users.id"), nullable=False, unique=True, index=True
    )

    # Bloc 1 — Vous
    prenom = db.Column(db.String(120), nullable=True)
    nom = db.Column(db.String(120), nullable=True)
    ville = db.Column(db.String(160), nullable=True)
    rayon = db.Column(db.String(24), nullable=True)
    tranche_age = db.Column(db.String(16), nullable=True)

    # Bloc 2 — Votre situation
    situation = db.Column(db.String(32), nullable=True)
    reconversion_scope = db.Column(db.String(32), nullable=True)

    # « Ton parcours » — level, kind of schooling, and the appetite that filters
    # the pistes by study length.
    diplome = db.Column(db.String(32), nullable=True)
    type_etudes = db.Column(db.String(32), nullable=True)
    intitule_etudes = db.Column(db.Text, nullable=True)
    appetence_etudes = db.Column(db.String(16), nullable=True)

    # Bloc 3 — Votre projet (+ optional job ad / fiche métier, extracted to text)
    projet = db.Column(db.Text, nullable=True)
    projet_document = db.Column(db.Text, nullable=True)

    # Bloc 4 — Contraintes pratiques. Free text, and the field warns against
    # naming a diagnosis: describe the effect on work, not the cause.
    contraintes_pratiques = db.Column(db.Text, nullable=True)

    # Bloc 6 — RGPD consent. Mandatory before the profile can be saved.
    consent_at = db.Column(db.DateTime, nullable=True)
    consent_version = db.Column(db.String(16), nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    sensitive = db.relationship(
        "SensitiveProfile",
        backref="profile",
        uselist=False,
        cascade="all, delete-orphan",
    )

    def to_dict(self) -> dict:
        """Never includes the sensitive half — that is the whole point of the
        split. Read it through SensitiveProfile explicitly if you need it."""
        return {
            "id": self.id,
            "prenom": self.prenom,
            "nom": self.nom,
            "ville": self.ville,
            "rayon": self.rayon,
            "tranche_age": self.tranche_age,
            "situation": self.situation,
            "diplome": self.diplome,
            "type_etudes": self.type_etudes,
            "intitule_etudes": self.intitule_etudes,
            "appetence_etudes": self.appetence_etudes,
            "reconversion_scope": self.reconversion_scope,
            "projet": self.projet,
            "projet_document": self.projet_document,
            "contraintes_pratiques": self.contraintes_pratiques,
            "consent_at": self.consent_at.isoformat() if self.consent_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class SensitiveProfile(db.Model):
    """Bloc 5 and the OETH flag, encrypted at rest.

    Access the payload through the `conditions` / `oeth` properties; the
    underlying columns hold Fernet tokens and are useless on their own — which
    is the intent for anything that dumps rows (log shipper, DB export, admin
    query).
    """

    __tablename__ = "sensitive_profiles"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    profile_id = db.Column(
        db.String(36), db.ForeignKey("profiles.id"), nullable=False, unique=True, index=True
    )

    # Fernet tokens (URL-safe base64), not raw bytes — Text is the right type.
    conditions_encrypted = db.Column(db.Text, nullable=True)
    oeth_encrypted = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # ── bloc 5 ───────────────────────────────────────────────────────────────
    @property
    def conditions(self) -> dict:
        """{family: {"state": ..., "point_fort": bool}} — {} when unfilled.

        Bloc 5 is optional for everyone (Parcours §11 recommendation), so an
        absent value is a normal state, not an error.
        """
        return crypto.decrypt_json(self.conditions_encrypted) or {}

    @conditions.setter
    def conditions(self, value: dict | None) -> None:
        self.conditions_encrypted = crypto.encrypt_json(value or {})

    # ── OETH ─────────────────────────────────────────────────────────────────
    @property
    def oeth(self) -> bool:
        return bool(crypto.decrypt_json(self.oeth_encrypted))

    @oeth.setter
    def oeth(self, value) -> None:
        self.oeth_encrypted = crypto.encrypt_json(bool(value))


def normalize_conditions(raw) -> dict:
    """Validate a bloc-5 payload into {family: {state, point_fort}}.

    Unknown families and states are dropped rather than raising: this data is
    optional, and a malformed entry should not cost the user their profile.
    """
    if not isinstance(raw, dict):
        return {}
    out = {}
    for family, entry in raw.items():
        if family not in CONDITION_FAMILIES or not isinstance(entry, dict):
            continue
        state = entry.get("state")
        if state not in CONDITION_STATES:
            continue
        out[family] = {
            "state": state,
            # "C'est un point fort" is a separate axis from the three states.
            # Tolerating a painful requirement is a differentiator; merely
            # preferring something is not — see prompt_context().
            "point_fort": bool(entry.get("point_fort")),
        }
    return out


# Requirements that few people tolerate. A "point fort" on one of these is
# what the report is allowed to valorise; a point fort on anything else is
# a preference, and preferences don't differentiate a candidate.
DIFFERENTIATING = {
    "rythme",
    "environnement",
    "deplacements",
    "effort_physique",
}


def prompt_context(conditions: dict) -> dict:
    """Shape bloc 5 for the prompt.

    Encodes the rule from the Parcours doc: « me convient » is never a
    strength. Only a point fort on a demanding requirement is a real
    differentiator, and only those are offered to the model as such.
    """
    strengths, adaptations, avoid = [], [], []
    for family, entry in (conditions or {}).items():
        state = entry.get("state")
        if entry.get("point_fort") and family in DIFFERENTIATING:
            strengths.append(family)
        if state == "possible_avec_adaptation":
            adaptations.append(family)
        elif state == "a_eviter":
            avoid.append(family)
    return {
        "points_forts": sorted(strengths),
        "possible_avec_adaptation": sorted(adaptations),
        "a_eviter": sorted(avoid),
    }
