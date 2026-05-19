import json
import re
import os
from datetime import datetime
from flask import current_app
import anthropic
from json_repair import repair_json

from ..extensions import db
from ..models.analysis import Analysis
from ..models.prompt_version import PromptVersion

_MODEL_HAIKU  = os.getenv("MODEL_FREE", "claude-haiku-4-5-20251001")
_MODEL_SONNET = os.getenv("MODEL_PAID", "claude-sonnet-4-6")

_HAIKU_SECTION_NOTE = (
    "\n\n[Instruction système : génère UNIQUEMENT les sections §1 à §4. "
    "N'inclus pas les sections §5 à §9.]"
)


def _get_client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


def _clean_model_id(model: str) -> str:
    return model.removeprefix("anthropic/")


def _select_model_by_tier(tier: str) -> tuple[str, int]:
    if tier == "sonnet":
        return _clean_model_id(_MODEL_SONNET), 8000
    return _clean_model_id(_MODEL_HAIKU), 8000


def _format_user_message(inputs: dict) -> str:
    tier = inputs.get("_tier", "haiku")
    base = f"""--- CV DU CANDIDAT ---
{inputs.get("cv_text", "").strip()}

--- CIBLE VISÉE ---
{inputs.get("cible_visee", "").strip()}

--- PROFIL ---
Prénom : {inputs.get("prenom", "")}
Tranche d'âge : {inputs.get("tranche_age", "")}
Localisation : {inputs.get("localisation", "")}
Situation actuelle : {inputs.get("situation_actuelle", "")}
Type de mobilité : {inputs.get("type_mobilite", "")}
Notes spécifiques : {inputs.get("notes_specifiques", "") or "Aucune note spécifique."}""".strip()
    if tier == "haiku":
        base += _HAIKU_SECTION_NOTE
    return base


def _extract_json_candidate(raw: str) -> str:
    """Pull the JSON string out of the raw model response."""
    stripped = raw.strip()
    if stripped.startswith("{"):
        return stripped
    for pattern in (r"```json\s*\n([\s\S]+)\n```", r"```\s*\n([\s\S]+)\n```"):
        m = re.search(pattern, raw)
        if m:
            return m.group(1).strip()
    start, end = raw.find("{"), raw.rfind("}")
    if start != -1 and end > start:
        return raw[start:end + 1]
    return raw


def _parse_output(raw: str) -> dict:
    candidate = _extract_json_candidate(raw)
    # Try strict parse first; fall back to json-repair for malformed AI output
    # (unescaped newlines, unescaped quotes inside strings, trailing commas, etc.)
    for s in (candidate, repair_json(candidate)):
        try:
            result = json.loads(s)
            if isinstance(result, dict):
                return result
        except (json.JSONDecodeError, ValueError):
            pass
    return {"1": {"title": "Analyse", "body_markdown": raw, "items": []}}


def stream_analysis(analysis_id: str):
    """SSE generator. Routes by _tier stored in inputs, streams via Anthropic SDK."""
    with current_app.app_context():
        analysis = Analysis.query.get(analysis_id)
        if not analysis:
            yield f"data: {json.dumps({'type': 'error', 'message': 'Analyse introuvable.'})}\n\n"
            return

        prompt = PromptVersion.query.filter_by(is_active=True).first()
        if not prompt:
            analysis.status = "error"
            db.session.commit()
            yield f"data: {json.dumps({'type': 'error', 'message': 'Aucun prompt actif.'})}\n\n"
            return

        tier = (analysis.inputs or {}).get("_tier", "haiku")
        model, max_tokens = _select_model_by_tier(tier)

        analysis.status = "running"
        analysis.prompt_version_id = prompt.id
        db.session.commit()

        full_response = ""

        try:
            client = _get_client()
            with client.messages.stream(
                model=model,
                max_tokens=max_tokens,
                system=prompt.system_prompt_text,
                messages=[{"role": "user", "content": _format_user_message(analysis.inputs)}],
            ) as stream:
                for text in stream.text_stream:
                    full_response += text
                    yield f"data: {json.dumps({'type': 'delta', 'text': text})}\n\n"

                final = stream.get_final_message()
                tokens_in  = final.usage.input_tokens
                tokens_out = final.usage.output_tokens

            output = _parse_output(full_response)
            analysis.status = "success"
            analysis.output = output
            analysis.raw_output = full_response
            analysis.tokens_in = tokens_in
            analysis.tokens_out = tokens_out
            analysis.completed_at = datetime.utcnow()
            db.session.commit()

            yield f"data: {json.dumps({'type': 'done', 'analysis_id': analysis_id})}\n\n"

        except Exception as exc:
            msg = str(exc).lower()
            analysis.status = "timeout" if "timeout" in msg or "timed out" in msg else "error"
            db.session.commit()
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"
