"""Willingness-to-pay probe, shown after a free report.

PM (2026-07-29): "À traiter comme un signal de hiérarchie, pas comme un prix
de vente : les gens déclarent toujours plus qu'ils ne paient." So this is
deliberately a ranking instrument — the buckets are ordered and coarse, and
nothing in the app reads it to set a price.
"""
from uuid import uuid4
from datetime import datetime

from ..extensions import db

# Ordered low → high. "je_ne_paierais_pas" is last on purpose: it is the floor
# of the scale, not a missing answer.
BUCKETS = (
    "moins_5",
    "5_10",
    "10_20",
    "plus_20",
    "je_ne_paierais_pas",
)

BUCKET_LABELS = {
    "moins_5": "Moins de 5 €",
    "5_10": "5 à 10 €",
    "10_20": "10 à 20 €",
    "plus_20": "Plus de 20 €",
    "je_ne_paierais_pas": "Je ne paierais pas",
}


class PriceFeedback(db.Model):
    __tablename__ = "price_feedback"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    analysis_id = db.Column(
        db.String(36), db.ForeignKey("analyses.id"), nullable=False, unique=True, index=True
    )
    # Was the diagnosis useful at all — asked alongside the price so a low
    # bucket can be read as "not useful" rather than "too expensive".
    useful = db.Column(db.Boolean, nullable=True)
    bucket = db.Column(db.String(24), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "analysis_id": self.analysis_id,
            "useful": self.useful,
            "bucket": self.bucket,
            "label": BUCKET_LABELS.get(self.bucket, self.bucket),
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
