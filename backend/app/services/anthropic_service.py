import json
import re
import os
import threading
import time
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


def _join(values, fallback: str) -> str:
    if isinstance(values, list) and values:
        return ", ".join(str(v).strip() for v in values if str(v).strip())
    if isinstance(values, str) and values.strip():
        return values.strip()
    return fallback


def _text(inputs: dict, key: str, fallback: str = "Non renseigné.") -> str:
    return (inputs.get(key) or "").strip() or fallback


def _profile_block(inputs: dict) -> list[str]:
    """The Profil de base, shared by all three parcours.

    Filled once and never re-asked (Parcours doc §1: "une information, une
    seule fois"), so every parcours message opens with the same block.
    """
    lines = [
        "--- PROFIL DE BASE ---",
        f"Prénom : {inputs.get('prenom', '')}",
        f"Nom : {(inputs.get('nom', '') or '').upper()}",
        f"Tranche d'âge : {_text(inputs, 'tranche_age')}",
        f"Localisation : {_text(inputs, 'ville') if inputs.get('ville') else _text(inputs, 'localisation')}",
        f"Rayon de recherche : {_text(inputs, 'rayon')}",
        f"Situation actuelle : {_text(inputs, 'situation') if inputs.get('situation') else _text(inputs, 'situation_actuelle')}",
    ]
    if inputs.get("reconversion_scope"):
        lines.append(f"Changement visé : {inputs['reconversion_scope']}")
    lines += [
        f"Projet : {_text(inputs, 'projet')}",
        f"Contraintes pratiques : {_text(inputs, 'contraintes_pratiques', 'Aucune contrainte déclarée.')}",
    ]
    return lines


def _conditions_block(inputs: dict) -> list[str]:
    """Bloc 5, already reduced to the three lists the report may use.

    The caller passes `_conditions` pre-shaped by profile.prompt_context(), so
    the raw answers never reach the model — only what it is allowed to say.
    A point fort here is a demanding requirement the person tolerates, which
    is the only kind that differentiates them.
    """
    ctx = inputs.get("_conditions") or {}
    if not any(ctx.get(k) for k in ("points_forts", "possible_avec_adaptation", "a_eviter")):
        return []
    return [
        "",
        "--- CONDITIONS DE TRAVAIL ---",
        f"Points forts (exigences que peu de gens tiennent) : {_join(ctx.get('points_forts'), 'Aucun.')}",
        f"Possible avec un aménagement : {_join(ctx.get('possible_avec_adaptation'), 'Aucun.')}",
        f"À éviter : {_join(ctx.get('a_eviter'), 'Aucun.')}",
    ]


def _rights_block(inputs: dict) -> list[str]:
    """Administrative level of the B3 handling (CDC §3.3).

    Never a diagnosis and never a medical term — the flag only tells the model
    which institutional schemes are open, and the report is forbidden from
    naming the status itself.
    """
    if not inputs.get("_oeth"):
        return []
    return [
        "",
        "--- DISPOSITIFS MOBILISABLES ---",
        "La personne est bénéficiaire de l'obligation d'emploi (OETH). Les dispositifs "
        "Agefiph / FIPHFP / Cap Emploi sont mobilisables. Ne jamais mentionner ce statut "
        "ni aucun terme médical dans le rapport : formuler uniquement en besoins et en "
        "aménagements.",
    ]


def _common_tail(inputs: dict) -> list[str]:
    return _conditions_block(inputs) + _rights_block(inputs)


def _format_user_message_p1(inputs: dict) -> str:
    """Parcours 1 — « J'ai une cible ». CV + target."""
    parts = [
        "--- CV DU CANDIDAT ---",
        _text(inputs, "cv_text"),
        "",
        "--- CIBLE VISÉE ---",
        _text(inputs, "cible_visee"),
    ]
    # Chemin B: the target was described rather than pasted, so the report
    # opens with a framing note. No lookup is performed (PM: framing note only
    # at launch — avoids the cost and the invented-data risk).
    if inputs.get("_chemin") == "B":
        parts += [
            "",
            "--- CADRAGE ---",
            "La cible a été décrite par la personne, pas fournie sous forme d'offre. "
            "Ouvrir le rapport par une note de cadrage : « analyse fondée sur le métier "
            "décrit ci-dessus, d'après votre description ».",
        ]
    parts += [""] + _profile_block(inputs)
    parts.append(f"Notes spécifiques : {_text(inputs, 'notes_specifiques', 'Aucune note spécifique.')}")
    return "\n".join(parts + _common_tail(inputs))


def _format_user_message_p2(inputs: dict) -> str:
    """Parcours 2 — « Je cherche ma direction ». A career, no target.

    Three questions, not four: the non-negotiable constraints already live in
    bloc 4 of the profile and health is covered for everyone by bloc 5, so
    re-asking them cost an abandonment for nothing (Parcours doc §5).
    """
    parts = [
        "--- CV OU EXPÉRIENCES ---",
        _text(inputs, "cv_text"),
        "",
        "--- QUESTIONS DE CADRAGE ---",
        f"Ce qui a donné le plus de satisfaction : {_text(inputs, 'satisfaction')}",
        f"Ce que la personne ne veut plus faire : {_text(inputs, 'refus')}",
        f"Raison principale du changement : {_text(inputs, 'raison_changement')}",
        "",
    ]
    return "\n".join(parts + _profile_block(inputs) + _common_tail(inputs))


def _format_user_message_p3(inputs: dict) -> str:
    """Parcours 3 — « Je pars de zéro ». No CV required.

    The life questionnaire is the input: informal activity — sport,
    volunteering, caring for a relative — is valid raw material, and the
    report's job is to reformulate it in professional language.
    """
    parts = [
        "--- QUESTIONNAIRE DE VIE ---",
        f"Ce que la personne a fait jusqu'ici : {_text(inputs, 'experiences')}",
        f"Ce qu'elle aime faire / sait faire : {_text(inputs, 'aime_faire')}",
        f"Ce qu'elle ne veut pas ou ne peut pas faire : {_text(inputs, 'refus')}",
        f"Contraintes pratiques déclarées ici : {_text(inputs, 'contraintes')}",
        f"Ce qu'est « un bon travail » pour elle : {_text(inputs, 'bon_travail')}",
    ]
    cv = (inputs.get("cv_text") or "").strip()
    if cv:
        parts += ["", "--- CV PARTIEL (facultatif) ---", cv]
    parts.append("")
    return "\n".join(parts + _profile_block(inputs) + _common_tail(inputs))


_FORMATTERS = {
    "1": _format_user_message_p1,
    "2": _format_user_message_p2,
    "3": _format_user_message_p3,
}


def _format_user_message(inputs: dict) -> str:
    parcours = registry.normalize((inputs or {}).get("_path"))
    return _FORMATTERS[parcours](inputs or {})


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


# ── Live progress ────────────────────────────────────────────────────────────
# The waiting screen used to animate a clock: it filled to 95 % in 48 s and then
# sat there until the row flipped to 'success'. A parcours 1 run measured 84 s
# on the free tier (4 sections) and 119 s on the paid one (9 sections) — so the
# paid tier, which the PM's review runs on, froze at 95 % for more than a
# minute and read as a hang. The percentage is now taken from the stream: each
# top-level `"key": {` is a section starting, which is a fact about the run and
# not a guess about its duration.

# French JSON output measures ~3.2-3.8 characters per output token. Only used
# before the first section key appears (markdown response, no structured
# output), where characters against the budget is the sole signal available.
_CHARS_PER_TOKEN = 3.6

# One row update per streamed chunk would be hundreds of writes per analysis.
_PROGRESS_INTERVAL_S = 2.0


def _section_open_re(keys: list[str]) -> re.Pattern:
    """Matches a top-level section object opening in the streamed JSON.

    The negative lookbehind drops `\\"4\\": {` written *inside* a body string —
    escaped there, plain here — so prose quoting a section can't advance the
    bar. Longest-first, like _md_section_re, so "VI" is never read as "V".
    """
    alt = "|".join(re.escape(k) for k in sorted(keys, key=len, reverse=True))
    return re.compile(rf'(?<!\\)"({alt})"\s*:\s*\{{')


def _stream_progress(acc: str, pattern: re.Pattern, total: int, budget_chars: int) -> int:
    """Percent complete for what has been streamed so far, 0-99.

    Sections already opened are finished except the last one, which is scaled
    by its length so far against the average of those already written — the
    stream calibrates itself, no per-parcours constant to keep in sync. Never
    returns 100: that is the row reaching 'success', never an estimate.
    """
    opens = [m.start() for m in pattern.finditer(acc)]
    if not opens:
        return min(int(100 * len(acc) / budget_chars), 90) if budget_chars else 0

    done = len(opens) - 1
    average = (opens[-1] - opens[0]) / done if done else budget_chars / max(total, 1)
    inner = min((len(acc) - opens[-1]) / average, 0.99) if average > 0 else 0.0
    return min(int(100 * (done + inner) / total), 99)


def _publish_progress(analysis_id: str, pct: int) -> None:
    """Write the percentage to the row the frontend polls, then hand the
    connection straight back — the stream it reports on runs for minutes, and
    holding a pooled connection across it is what leaves rows stuck 'running'
    (see _run_analysis)."""
    try:
        Analysis.query.filter_by(id=analysis_id).update({"progress": pct})
        db.session.commit()
    finally:
        db.session.remove()


class ProgressReporter:
    """Turns the accumulating stream into published percentages.

    Throttled (one write per interval), monotonic (the structured-output retry
    restarts the stream from zero and must not run the bar backwards) and
    silent on failure (progress is decoration; it must never take down the
    analysis it is reporting on).
    """

    def __init__(self, analysis_id, keys, budget_chars,
                 writer=None, clock=time.monotonic, min_interval=None):
        self._analysis_id = analysis_id
        self._pattern = _section_open_re(list(keys))
        self._total = len(keys)
        self._budget_chars = budget_chars
        # Resolved here rather than as default arguments: a default binds the
        # function object at class-definition time, which no test can replace.
        self._writer = writer or _publish_progress
        self._clock = clock
        self._min_interval = _PROGRESS_INTERVAL_S if min_interval is None else min_interval
        self._published = 0
        self._last_write = None

    def update(self, acc: str) -> None:
        now = self._clock()
        if self._last_write is not None and now - self._last_write < self._min_interval:
            return
        self._last_write = now
        pct = _stream_progress(acc, self._pattern, self._total, self._budget_chars)
        if pct <= self._published:
            return
        self._published = pct
        try:
            self._writer(self._analysis_id, pct)
        except Exception:
            pass


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
        # Publishes what the stream has actually produced, so the waiting
        # screen keeps moving through a 2-minute paid generation.
        reporter = ProgressReporter(
            analysis_id,
            keys=_section_keys(path, tier),
            budget_chars=int(max_tokens * _CHARS_PER_TOKEN),
        )
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
                        reporter.update(acc)
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
        analysis.progress = 100
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
