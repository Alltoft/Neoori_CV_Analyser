import json
import re
import os
import threading
from datetime import datetime
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


_SUB_PROFILE_LABELS = {
    "b1": "B1 — Jeune en insertion",
    "b2": "B2 — Reprise après pause",
    "b3": "B3 — Reprise après maladie ou handicap",
}


def _join(values, fallback: str) -> str:
    if isinstance(values, list) and values:
        return ", ".join(str(v).strip() for v in values if str(v).strip())
    if isinstance(values, str) and values.strip():
        return values.strip()
    return fallback


def _format_user_message_b(inputs: dict) -> str:
    sub = (inputs.get("_sub_profile") or "b1").lower()
    label = _SUB_PROFILE_LABELS.get(sub, _SUB_PROFILE_LABELS["b1"])

    parts = [
        "--- SOUS-PROFIL ---",
        label,
        "",
        "--- IDENTITÉ ---",
        f"Prénom et nom : {inputs.get('nom', '').strip()}",
        "",
        "--- PRÉFÉRENCES ---",
        f"Ce que la personne aime faire : {_join(inputs.get('aime'), 'Non renseigné.')}",
        f"Situations où la personne se sent compétente : {_join(inputs.get('competent'), 'Non renseigné.')}",
        f"Ce que la personne refuse dans un travail : {_join(inputs.get('refuse'), 'Aucun refus déclaré.')}",
    ]

    if sub == "b2":
        parts += [
            "",
            "--- CONTEXTE SPÉCIFIQUE ---",
            f"Activité pendant la pause : {(inputs.get('pause_activite') or '').strip() or 'Non renseigné.'}",
            f"Contraintes pratiques : {_join(inputs.get('contraintes_pratiques'), 'Aucune contrainte déclarée.')}",
        ]
    elif sub == "b3":
        parts += [
            "",
            "--- CONTEXTE SPÉCIFIQUE ---",
            f"Contraintes fonctionnelles : {_join(inputs.get('contraintes_b3'), 'Aucune contrainte déclarée.')}",
            f"Accompagnement existant : {(inputs.get('accompagnement') or '').strip() or 'Non renseigné.'}",
        ]

    if sub == "b3":
        cv = (inputs.get("cv_b3") or "").strip()
        parts += [
            "",
            "--- CV OPTIONNEL (B3 uniquement) ---",
            cv if cv else "Non fourni.",
        ]

    return "\n".join(parts)


def _format_user_message(inputs: dict) -> str:
    if (inputs or {}).get("_path") == "B":
        return _format_user_message_b(inputs)
    tier = inputs.get("_tier", "haiku")
    base = f"""--- CV DU CANDIDAT ---
{inputs.get("cv_text", "").strip()}

--- CIBLE VISÉE ---
{inputs.get("cible_visee", "").strip()}

--- PROFIL ---
Prénom : {inputs.get("prenom", "")}
Nom : {(inputs.get("nom", "") or "").upper()}
Tranche d'âge : {inputs.get("tranche_age", "")}
Localisation : {inputs.get("localisation", "")}
Situation actuelle : {inputs.get("situation_actuelle", "")}
Type de mobilité : {" + ".join(inputs["type_mobilite"]) if isinstance(inputs.get("type_mobilite"), list) else inputs.get("type_mobilite", "")}
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


def _run_analysis(analysis_id: str, app) -> None:
    """Run a single analysis to completion. Writes status + output to DB.

    Designed to run inside a background daemon thread spawned by the
    `POST /analyses/` route. Internally still uses the Anthropic streaming
    SDK so the upstream HTTP request stays alive for long generations
    (Sonnet at 8000 tokens can take several minutes), but no SSE is sent
    to the client — the frontend polls `GET /analyses/<id>` for status.
    """
    with app.app_context():
        analysis = Analysis.query.get(analysis_id)
        if not analysis:
            return

        inputs = analysis.inputs or {}
        path = inputs.get("_path", "A")
        prompt = PromptVersion.query.filter_by(is_active=True, path=path).first()
        if not prompt:
            analysis.status = "error"
            analysis.raw_output = f"Aucun prompt actif pour le chemin {path}."
            db.session.commit()
            return

        # Chemin B is free + Sonnet for all users (decision 4.6 / 4.7).
        tier = "sonnet" if path == "B" else inputs.get("_tier", "haiku")
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
                final = stream.get_final_message()
                tokens_in = final.usage.input_tokens
                tokens_out = final.usage.output_tokens

            output = _parse_output(full_response)
            analysis.status = "success"
            analysis.output = output
            analysis.raw_output = full_response
            analysis.tokens_in = tokens_in
            analysis.tokens_out = tokens_out
            analysis.completed_at = datetime.utcnow()
            db.session.commit()

        except Exception as exc:
            msg = str(exc).lower()
            analysis.status = "timeout" if ("timeout" in msg or "timed out" in msg) else "error"
            analysis.raw_output = str(exc)[:2000]
            db.session.commit()


def start_analysis(analysis_id: str, app) -> None:
    """Spawn a daemon thread that runs the analysis in the background."""
    threading.Thread(
        target=_run_analysis,
        args=(analysis_id, app),
        daemon=True,
    ).start()
