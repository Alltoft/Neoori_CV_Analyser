from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, verify_jwt_in_request
from ..extensions import db
from ..models.analysis import Analysis
from ..models.counselor_note import CounselorNote

counselor_bp = Blueprint("counselor", __name__)


@counselor_bp.get("/<share_token>")
def get_by_share_token(share_token):
    """
    Public share link — returns counselor view (sections 1, 4, 5 only).
    No auth required to read; auth required to write notes.
    """
    analysis = Analysis.query.filter_by(share_token=share_token).first_or_404()

    if analysis.status != "success":
        return jsonify({"error": "Analyse non disponible."}), 404

    return jsonify({"analysis": analysis.to_dict(audience="counselor")}), 200


@counselor_bp.put("/<share_token>/notes")
@jwt_required()
def upsert_notes(share_token):
    """Save or update counselor private notes. Auth required. Not shared with candidate."""
    counselor_id = get_jwt_identity()
    analysis = Analysis.query.filter_by(share_token=share_token).first_or_404()

    data = request.get_json(silent=True) or {}
    body = data.get("body", "")

    note = CounselorNote.query.filter_by(
        analysis_id=analysis.id,
        counselor_id=counselor_id,
    ).first()

    if note:
        note.body = body
    else:
        note = CounselorNote(
            analysis_id=analysis.id,
            counselor_id=counselor_id,
            body=body,
        )
        db.session.add(note)

    db.session.commit()
    return jsonify({"note": note.to_dict()}), 200


@counselor_bp.get("/<share_token>/notes")
@jwt_required()
def get_notes(share_token):
    """Retrieve this counselor's private notes for this analysis."""
    counselor_id = get_jwt_identity()
    analysis = Analysis.query.filter_by(share_token=share_token).first_or_404()

    note = CounselorNote.query.filter_by(
        analysis_id=analysis.id,
        counselor_id=counselor_id,
    ).first()

    return jsonify({"note": note.to_dict() if note else None}), 200
