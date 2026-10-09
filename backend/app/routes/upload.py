from flask import Blueprint, request, jsonify
from ..services.pdf_service import extract_text_from_pdf

upload_bp = Blueprint("upload", __name__)

ALLOWED_MIME = {"application/pdf"}
MAX_SIZE = 10 * 1024 * 1024


def _extract_pdf_from_request() -> tuple[str | None, tuple | None]:
    """Extract text from uploaded PDF. Returns (text, error_response) tuple."""
    if "file" not in request.files:
        return None, (jsonify({"error": "Aucun fichier reçu."}), 400)
    file = request.files["file"]
    if file.mimetype not in ALLOWED_MIME:
        return None, (jsonify({"error": "Format non supporté. PDF uniquement."}), 415)
    file_bytes = file.read()
    if len(file_bytes) > MAX_SIZE:
        return None, (jsonify({"error": "Fichier trop volumineux (10 Mo maximum)."}), 413)
    text = extract_text_from_pdf(file_bytes)
    if not text.strip():
        return None, (jsonify({"error": "Impossible d'extraire le texte. PDF scanné ou protégé ?"}), 422)
    return text, None


# Open to signed-out visitors: the parcours 1 form is (four-doors spec, ruling
# 1). The text is extracted in memory and returned, never stored; nginx's
# `analyses` zone limits these per address (decision 39).
@upload_bp.post("/cv")
def upload_cv():
    text, err = _extract_pdf_from_request()
    if err:
        return err
    return jsonify({"cv_text": text, "char_count": len(text)}), 200


@upload_bp.post("/projet")
def upload_projet():
    text, err = _extract_pdf_from_request()
    if err:
        return err
    return jsonify({"projet_text": text, "char_count": len(text)}), 200
