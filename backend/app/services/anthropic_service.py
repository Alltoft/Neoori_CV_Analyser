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
from . import section_registry as registry
from . import tiers


def _get_client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


def _select_model_by_tier(tier: str) -> tuple[str, int]:
    """(model id, max_tokens) for a tier. See services/tiers.py."""
    return tiers.model_for(tier)


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
    if registry.normalize((inputs or {}).get("_path")) == "3":
        return _format_user_message_b(inputs)
    return f"""--- CV DU CANDIDAT ---
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


# ── Structured output enforcement ────────────────────────────────────────────
# The system prompt lives in DB and is freely edited by the PM (often pasted as
# prose with no JSON instructions — that's expected). Structure is therefore
# enforced at the API layer with a JSON-schema output format, never via the
# prompt text. See https://platform.claude.com/docs/en/build-with-claude/structured-outputs

def _section_keys(path: str, tier: str) -> list[str]:
    return registry.section_keys(path, tiers.normalize(tier))


def _build_output_schema(path: str, tier: str) -> dict:
    plan = tiers.normalize(tier)
    entries = registry.sections(path, plan)
    properties = {}
    for s in entries:
        k = s["key"]
        tags_only = s["render"] == registry.TAGS
        properties[k] = {
            "type": "object",
            "description": f"Section {k} — {s['title']}",
            "properties": {
                "title": {"type": "string"},
                "body_markdown": {
                    "type": "string",
                    "description": (
                        "Chaîne vide — cette section n'est constituée que de tags."
                        if tags_only
                        else "Contenu markdown de la section."
                    ),
                },
                "items": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Les tags de la section."
                        if tags_only
                        else "Tags ou points courts. Tableau vide si non applicable."
                    ),
                },
            },
            "required": ["title", "body_markdown", "items"],
            "additionalProperties": False,
        }
    keys = [s["key"] for s in entries]
    return {
        "type": "object",
        "properties": properties,
        "required": keys,
        "additionalProperties": False,
    }


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


def _md_section_re(keys: list[str]) -> re.Pattern:
    """Heading matcher for a parcours' key set.

    Matches "## §1 Titre", "### Section A : Titre", "**§IV — Titre**".
    The alternation is built from the actual keys rather than a generic
    character class, so "VI" can't be read as "V" and parcours 2's letter
    keys can't collide with parcours 3's Roman numerals. Longest-first
    ordering is what makes that work.
    """
    alt = "|".join(re.escape(k) for k in sorted(keys, key=len, reverse=True))
    return re.compile(
        rf"^(?:#{{1,4}}\s*|\*\*\s*)?(?:§\s*|section\s+)({alt})\b[\s:.\-—·]*(.*?)(?:\*\*)?\s*$",
        re.IGNORECASE | re.MULTILINE,
    )


def _split_markdown_sections(raw: str, path: str) -> dict | None:
    """Fallback parser: split a prose/markdown response on section headings.

    Returns None when fewer than 2 headings are found (not a sectioned
    document — let the caller use the last-resort fallback).
    """
    known = registry.titles(path)
    matches = list(_md_section_re(list(known)).finditer(raw))
    # Keep only the first occurrence of each section key, in order
    seen: dict = {}
    for m in matches:
        key = _canonical_key(m.group(1), known)
        if key and key not in seen:
            seen[key] = m
    if len(seen) < 2:
        return None

    ordered = list(seen.items())
    result = {}
    for i, (key, m) in enumerate(ordered):
        title = m.group(2).strip().strip("*").strip() or known.get(key, f"Section {key}")
        start = m.end()
        end = ordered[i + 1][1].start() if i + 1 < len(ordered) else len(raw)
        body = raw[start:end].strip().strip("-").strip()
        result[key] = {"title": title, "body_markdown": body, "items": []}
    return result


def _canonical_key(matched: str, known: dict[str, str]) -> str | None:
    """Map a case-insensitive heading capture back to its registry key."""
    if matched in known:
        return matched
    lowered = matched.lower()
    for k in known:
        if k.lower() == lowered:
            return k
    return None


def _parse_output(raw: str, path: str = registry.DEFAULT_PARCOURS) -> dict:
    valid = set(registry.titles(path))
    candidate = _extract_json_candidate(raw)
    # Try strict parse first; fall back to json-repair for malformed AI output
    # (unescaped newlines, unescaped quotes inside strings, trailing commas, etc.)
    for s in (candidate, repair_json(candidate)):
        try:
            result = json.loads(s)
            if isinstance(result, dict) and any(k in valid for k in result):
                return result
        except (json.JSONDecodeError, ValueError):
            pass
    # Markdown response (e.g. legacy analyses, or structured output disabled):
    # split on section headings so each one still lands in its own slot.
    sections = _split_markdown_sections(raw, path)
    if sections:
        return sections
    first_key = registry.section_keys(path)[0]
    return {first_key: {"title": "Analyse", "body_markdown": raw, "items": []}}


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
        path = registry.normalize(inputs.get("_path"))
        prompt = PromptVersion.query.filter_by(is_active=True, path=path).first()
        if not prompt:
            analysis.status = "error"
            analysis.raw_output = f"Aucun prompt actif pour le chemin {path}."
            db.session.commit()
            return

        # Chemin B is free + Sonnet for all users (decision 4.6 / 4.7).
        # Parcours 3 runs on the paid model for everyone (free for the
        # vulnerable populations it serves).
        tier = tiers.PAID if path == "3" else tiers.normalize(inputs.get("_tier"))
        model, max_tokens = _select_model_by_tier(tier)

        analysis.status = "running"
        analysis.prompt_version_id = prompt.id
        db.session.commit()

        # Capture everything we need, then RELEASE the DB connection for the
        # duration of the (multi-minute) Anthropic stream. Holding a pooled
        # connection across the stream lets the DB server drop it as idle, so
        # the final commit fails with "Lost connection" and the row is stuck
        # in 'running'. pool_pre_ping only validates on checkout, not while a
        # connection is held — so we must not hold one here.
        system_prompt = prompt.system_prompt_text
        user_message = _format_user_message(inputs)
        schema = _build_output_schema(path, tier)
        db.session.remove()

        full_response = ""
        tokens_in = tokens_out = None
        error_exc = None
        try:
            client = _get_client()
            request_kwargs = dict(
                model=model,
                max_tokens=max_tokens,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}],
                # Structured outputs: guarantees the response is valid JSON
                # matching the parcours' section schema, no matter how the PM
                # words the system prompt. Passed via extra_body so it works on
                # any SDK version (it merges into the raw request payload).
                extra_body={
                    "output_config": {
                        "format": {"type": "json_schema", "schema": schema}
                    }
                },
            )

            def _run_stream(kwargs):
                acc = ""
                with client.messages.stream(**kwargs) as stream:
                    for text in stream.text_stream:
                        acc += text
                    final = stream.get_final_message()
                return acc, final.usage.input_tokens, final.usage.output_tokens

            try:
                full_response, tokens_in, tokens_out = _run_stream(request_kwargs)
            except anthropic.BadRequestError:
                # Structured outputs rejected (e.g. old API surface) — degrade
                # to a plain call; _parse_output still handles JSON or markdown.
                request_kwargs.pop("extra_body", None)
                full_response, tokens_in, tokens_out = _run_stream(request_kwargs)
        except Exception as exc:
            error_exc = exc

        # Re-acquire a fresh, pre-pinged connection to write the result.
        analysis = Analysis.query.get(analysis_id)
        if analysis is None:
            return
        if error_exc is not None:
            msg = str(error_exc).lower()
            analysis.status = "timeout" if ("timeout" in msg or "timed out" in msg) else "error"
            analysis.raw_output = str(error_exc)[:2000]
            db.session.commit()
            return

        analysis.status = "success"
        analysis.output = _parse_output(full_response, path)
        analysis.raw_output = full_response
        analysis.tokens_in = tokens_in
        analysis.tokens_out = tokens_out
        analysis.completed_at = datetime.utcnow()
        db.session.commit()


def start_analysis(analysis_id: str, app) -> None:
    """Spawn a daemon thread that runs the analysis in the background."""
    threading.Thread(
        target=_run_analysis,
        args=(analysis_id, app),
        daemon=True,
    ).start()
