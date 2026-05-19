from flask import Blueprint, request, jsonify
from ..services.pdf_service import extract_text_from_pdf

upload_bp = Blueprint("upload", __name__)

ALLOWED_MIME = {"application/pdf"}


@upload_bp.post("/cv")
def upload_cv():
    """
    Accept a PDF, extract plain text, return it.
    The client then includes cv_text in the analysis inputs payload.
    """
    if "file" not in request.files:
        return jsonify({"error": "Aucun fichier reçu."}), 400

    file = request.files["file"]

    if file.mimetype not in ALLOWED_MIME:
        return jsonify({"error": "Format non supporté. PDF uniquement."}), 415

    file_bytes = file.read()
    if len(file_bytes) > 10 * 1024 * 1024:
        return jsonify({"error": "Fichier trop volumineux (10 Mo maximum)."}), 413

    text = extract_text_from_pdf(file_bytes)

    if not text.strip():
        return jsonify({"error": "Impossible d'extraire le texte. PDF scanné ou protégé ?"}), 422

    return jsonify({"cv_text": text, "char_count": len(text)}), 200
