"""The voyage's two AI calls: the session-0 phrase and the six-section portrait.

Same discipline as anthropic_service._run_analysis: a daemon thread, the DB
connection released before the stream, a fresh session to write the result,
status -> "error" with the message on failure. The user message and the schema
are built BEFORE db.session.remove(), never from an ORM object held across the
stream.

Two things are enforced in code rather than in prompt prose, because the prompt
text is the PM's to rewrite at any moment from /admin/prompts:

  * structure — the portrait's six keys come from a JSON-schema output_config
    passed via extra_body, exactly as the analysis runner does it;
  * vocabulary — leak_check() scans the returned prose for the framework words
    the person must never read and retries once with a corrective turn. What
    happens next depends on who reads the text first: a portrait that still
    leaks is kept and flagged for the counselor who validates it; a session-0
    phrase that still leaks is refused, because nobody reads it before the
    person does.

Nothing here writes an answer, a score or a portrait sentence to a log.
"""
import json
import re
import threading
import unicodedata

import anthropic
from json_repair import repair_json

from ...extensions import db
from ...models.profile import Profile
from ...models.prompt_version import PromptVersion
from ...models.voyage import Voyage
from .. import prompt_slots
from .. import tiers
from ..anthropic_service import _extract_json_candidate, _get_client
from . import bank
from . import scoring

# ── slots and budgets ────────────────────────────────────────────────────────

MICRO_SLOT = prompt_slots.VOYAGE_MICRO
PORTRAIT_SLOT = prompt_slots.VOYAGE_PORTRAIT

# The tier's own max_tokens (8000) is discarded: one sentence does not need it,
# and the portrait is deliberately capped below it.
MICRO_MAX_TOKENS = 200
PORTRAIT_MAX_TOKENS = 3000
MICRO_WORDS = (15, 25)          # the counselor manual's « 1 phrase, 15-25 mots »

PORTRAIT_KEYS = ("accroche", "qui_tu_es", "vibrer", "besoins", "chemins", "pas_encore")

# The counselor manual's page-20 template, in order. Mirrored in phase 3's
# frontend portrait types.
PORTRAIT_TITLES = {
    "accroche": "Phrase d'accroche",
    "qui_tu_es": "Qui tu es",
    "vibrer": "Ce qui te fait vibrer",
    "besoins": "Ce dont tu as besoin",
    "chemins": "Les chemins possibles",
    "pas_encore": "Ce que ton portrait ne dit pas encore",
}

FLAG_VOCABULAIRE = "vocabulaire"    # the only value ever written into portrait["flags"]
ERROR_MAX_CHARS = 500               # the encrypted payload's `error` key is capped

# ── user-message section headers ─────────────────────────────────────────────

HEADER_PROFIL = "--- PROFIL DE BASE ---"      # reused from anthropic_service._profile_block
HEADER_SESSION_0 = "--- SESSION 0 ---"
HEADER_CHOISI = "--- CE QUE TU AS CHOISI ---"
HEADER_SYNTHESE = "--- SYNTHÈSE ---"

# The manual weights an ambivalence x1.5 when writing the portrait. It is the
# only figure either message is allowed to carry.
WEIGHT_NOTE = " (à pondérer ×1,5)"


# ── the portrait's output schema ─────────────────────────────────────────────
# Structure is enforced at the API layer, never via the prompt text: the PM
# rewrites the prompt freely and the six sections must survive it.
# See https://platform.claude.com/docs/en/build-with-claude/structured-outputs

def _portrait_schema() -> dict:
    return {
        "type": "object",
        "properties": {
            "accroche": {"type": "string",
                         "description": "Une phrase. Une métaphore unique. Jamais « Tu es… ». "
                                        "Jamais un métier nommé."},
            "qui_tu_es": {"type": "string",
                          "description": "5 à 7 phrases de prose. Mode de fonctionnement, énergie. "
                                         "Aucune liste."},
            "vibrer": {"type": "string",
                       "description": "4 à 6 phrases de prose. Motivations, source d'énergie, sens."},
            "besoins": {"type": "string",
                        "description": "5 à 7 phrases de prose. Cadre physique, cognitif et "
                                       "relationnel, formulé en préférences légitimes."},
            "chemins": {"type": "string",
                        "description": "4 à 5 phrases de prose. Familles d'environnements — "
                                       "« les gens qui… », « les endroits où… ». Jamais un métier."},
            "pas_encore": {"type": "string",
                           "description": "1 à 2 phrases. Une question ouverte que les sessions ne "
                                          "tranchent pas."},
        },
        "required": list(PORTRAIT_KEYS),
        "additionalProperties": False,
    }


# ── leak check ───────────────────────────────────────────────────────────────
# Layered, exactly as the spec asks: the prompt forbids these words, this scan
# catches what survives, and a counselor validates before the person reads it.
#
# scoring.INTRO_EXTRA, bank.STYLE_PLAIN and every `plain` / `plain_pos` /
# `plain_neg` / `tension` string in the bank are free of all seventeen — that is
# why intro_extra says « plutôt tourné(e) vers les autres » and not
# « extraversion ». test_voyage_generation.py holds that line for the two
# message builders.

LEAK_PATTERNS = (
    "névrotisme",
    "neuroticisme",
    "big five",
    "riasec",
    "schwartz",
    "sdt",
    "dunn",
    "kahneman",
    "dweck",
    "frankl",
    "logothérapie",
    "conscienciosité",
    "agréabilité",
    "extraversion",
    "introversion",
    "score",
    "trait",
)


def _fold(text: str) -> str:
    """Lowercase and drop combining marks, so « névrotisme » and « nevrotisme »
    are the same string and one pattern catches both."""
    decomposed = unicodedata.normalize("NFD", str(text or "").lower())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def _pattern(raw: str) -> re.Pattern:
    """One compiled matcher for one banned word.

    Word-boundary matching is what keeps « trait » from firing inside
    « portrait » and « score » from firing inside « scorer ». Inside a
    multi-word pattern any whitespace or hyphen will do, so « Big-Five » is
    caught as well as « big five ». The optional trailing `s` is deliberate:
    « tes traits de personnalité » and « tes scores » are the same leak as the
    singular, and the false positive it buys — « il score un but » — costs one
    corrective turn, never a broken portrait.
    """
    body = r"[\s\-]+".join(re.escape(word) for word in _fold(raw).split())
    return re.compile(rf"\b{body}s?\b")


_LEAK_RE = tuple((pattern, _pattern(pattern)) for pattern in LEAK_PATTERNS)


def leak_check(sections: dict[str, str] | None) -> list[str]:
    """Framework vocabulary that survived into the portrait.

    Returns the offending words, lowercased, de-duplicated, sorted — [] when
    clean. Matching is word-boundary, case-insensitive and diacritic-folded on
    both the text and the pattern.
    """
    haystack = _fold(" ".join(str(v or "") for v in (sections or {}).values()))
    return sorted({pattern for pattern, rx in _LEAK_RE if rx.search(haystack)})


# ── message builders ─────────────────────────────────────────────────────────
# Pure functions, called before db.session.remove(). The reduction discipline is
# models/profile.prompt_context()'s: the model receives only what it is allowed
# to say, so a rule can be enforced by a test rather than hoped for in prose.


def _micro_user_message(synthesis: dict, prenom: str | None) -> str:
    """Session 0 in plain words: the three strongest pulls and the hesitations.

    No number, no axis id, no framework name. `plain` and `tension` come
    straight from the bank's AXES table, which is where that wording has its
    single home (contracts § A.2).
    """
    s0 = (synthesis or {}).get("s0") or {}
    blocks: list[list[str]] = []

    if str(prenom or "").strip():
        blocks.append([HEADER_PROFIL, f"Prénom : {str(prenom).strip()}"])

    session_0: list[str] = []
    attractions = [a.get("plain") for a in s0.get("top3") or [] if a.get("plain")]
    if attractions:
        session_0.append(f"Ce qui l'attire le plus : {', '.join(attractions)}")
    tensions = [t.get("tension") for t in s0.get("tensions") or [] if t.get("tension")]
    if tensions:
        session_0.append(f"Autant coché des deux côtés sur : {' · '.join(tensions)}")
    if session_0:
        blocks.append([HEADER_SESSION_0] + session_0)

    return "\n\n".join("\n".join(block) for block in blocks)


_PROFILE_LABELS = (
    ("prenom", "Prénom"),
    ("tranche_age", "Tranche d'âge"),
    ("situation", "Situation actuelle"),
    ("projet", "Projet"),
)


def _clean(value) -> str:
    """A field's value, stripped — "" when it is missing or only whitespace.

    One rule in one place for every free-text field either builder reads: a
    label with nothing after it (« Rapport au risque :   ») is worse than no
    label, and whitespace is truthy, so the strip has to happen before the
    emptiness test rather than after.
    """
    return str(value or "").strip()


def _profile_lines(profile_fields: dict) -> list[str]:
    """The four Profil de base fields, each omitted when empty.

    « une information, une seule fois » (Parcours doc §1): the portrait reuses
    the prénom, the age bracket and the situation the profile already holds, so
    the voyage never asks for them again.
    """
    lines = []
    for key, label in _PROFILE_LABELS:
        value = _clean((profile_fields or {}).get(key))
        if value:
            lines.append(f"{label} : {value}")
    return lines


def _choice_lines(responses: dict) -> list[str]:
    """One line per scene: the scene's own title, then the person's own words.

    `plain` is the short plain-French descriptor authored beside each option;
    the scoring tag on that option never leaves the server (spec decision 6).
    Session 0 contributes nothing here — it reaches the model through the
    synthesis block only.
    """
    lines = []
    for n in ("1", "2", "3", "4", "5"):
        for item in bank.items(n):
            chosen = scoring.chosen_option(responses, item["id"]) or {}
            plain = chosen.get("plain")
            if plain:
                lines.append(f"{item['title']} : {plain}")
    return lines


def _synthesis_lines(synthesis: dict) -> list[str]:
    """The counselor's page-18 sheet, reduced to plain French.

    Nothing numeric survives: no axis score, no RIASEC point, no level word. The
    universe names (Réaliste, Investigateur…) and the three need words
    (autonomie, appartenance, competence) are the deliberate exceptions — they
    are ordinary French and the restitution guide says them out loud.

    The counselor-only fields (s4["vendredi"], s5["rapport_echec"],
    s5["rapport_flou"], the Big Five levels, Schwartz) are not here on purpose:
    they belong to the synthesis sheet, not to the portrait's raw material.
    """
    synthesis = synthesis or {}
    s0 = synthesis.get("s0") or {}
    riasec = synthesis.get("riasec") or {}
    s2 = synthesis.get("s2") or {}
    s3 = synthesis.get("s3") or {}
    s4 = synthesis.get("s4") or {}
    s5 = synthesis.get("s5") or {}

    lines = []

    univers = [t.get("univers") for t in riasec.get("top3") or [] if t.get("univers")]
    if univers:
        lines.append(f"Univers dominants : {', '.join(univers)}")

    attractions = [a.get("plain") for a in s0.get("top3") or [] if a.get("plain")]
    if attractions:
        lines.append(f"Ce qui l'attire le plus dans dix ans : {', '.join(attractions)}")

    tensions = [t.get("tension") for t in s0.get("tensions") or [] if t.get("tension")]
    if tensions:
        lines.append(
            f"Autant coché des deux côtés sur : {' · '.join(tensions)}{WEIGHT_NOTE}")

    besoins = [b for b in s2.get("sdt_dominant") or [] if b]
    if besoins:
        lines.append(f"Besoin dominant : {', '.join(besoins)}")

    # The tag itself never travels — bank.STYLE_PLAIN is what the model reads.
    styles = [bank.STYLE_PLAIN[s] for s in s3.get("style_dominant") or []
              if s in bank.STYLE_PLAIN]
    if styles:
        lines.append(f"Façon de fonctionner : {' · '.join(styles)}")

    # s4 and s5 strip before the emptiness test, exactly the way _profile_lines
    # does. Not because they are free text -- they are not: score_s4/score_s5
    # read bank-authored option labels off chosen_option(), the same as S1-S3,
    # and the one channel the person actually composes (responses["billets"])
    # never reaches either builder. They strip because they are the two blocks
    # whose values a counselor may one day edit, and because one strip rule in
    # one place beats two rules that agree today.
    cadre = [v for v in (_clean(s4.get(k))
                         for k in ("espace", "rythme", "equipe", "manager")) if v]
    if cadre:
        lines.append(f"Cadre : {' · '.join(cadre)}")
    irritant = _clean(s4.get("irritant"))
    if irritant:
        lines.append(f"Ce qui l'épuise : {irritant}")

    for key, label in (("risque", "Rapport au risque"),
                       ("valeur_centrale", "Ce qui la met en colère"),
                       ("trace", "La trace voulue"),
                       ("sacrifice", "Prête à sacrifier"),
                       ("vivant", "Se sent vivant(e) quand")):
        value = _clean(s5.get(key))
        if value:
            lines.append(f"{label} : {value}")

    return lines


def _portrait_user_message(synthesis: dict, responses: dict, profile_fields: dict) -> str:
    """Everything the portrait call is allowed to know, in three blocks.

    A block whose lines are all empty is omitted with its header.
    """
    blocks = []
    for header, lines in ((HEADER_PROFIL, _profile_lines(profile_fields)),
                          (HEADER_CHOISI, _choice_lines(responses)),
                          (HEADER_SYNTHESE, _synthesis_lines(synthesis))):
        if lines:
            blocks.append([header] + lines)
    return "\n\n".join("\n".join(block) for block in blocks)


# ── the streamed call ────────────────────────────────────────────────────────


def _stream_text(model: str, system_prompt: str, messages: list,
                 max_tokens: int, schema: dict | None) -> tuple[str, int, int]:
    """One streamed call. Returns (text, tokens_in, tokens_out).

    Streaming keeps the upstream HTTP request alive for long generations; no SSE
    reaches the client, which polls GET /api/voyage instead. Structured output
    goes through extra_body so it works on any SDK version, and a
    BadRequestError degrades to a plain call — the same fallback
    anthropic_service._run_analysis uses when the API surface refuses
    output_config.
    """
    client = _get_client()
    kwargs = dict(
        model=model,
        max_tokens=max_tokens,
        system=system_prompt,
        messages=list(messages),
    )
    if schema is not None:
        kwargs["extra_body"] = {
            "output_config": {"format": {"type": "json_schema", "schema": schema}}
        }

    def _run(call_kwargs):
        acc = ""
        with client.messages.stream(**call_kwargs) as stream:
            for chunk in stream.text_stream:
                acc += chunk
            final = stream.get_final_message()
        return acc, final.usage.input_tokens, final.usage.output_tokens

    try:
        return _run(kwargs)
    except anthropic.BadRequestError:
        # Only worth retrying if the schema is what the API refused. With no
        # extra_body there is nothing to degrade to, and re-sending an identical
        # request bills twice for the same 400.
        if "extra_body" not in kwargs:
            raise
        kwargs.pop("extra_body")
        return _run(kwargs)


def _one_sentence(raw: str) -> str:
    """Normalise the model's answer to a single line.

    The prompt asks for one sentence and nothing else; this only removes the
    wrapping it sometimes adds anyway (quotes, a leading dash, a trailing
    newline). It never truncates: a phrase that came back too long is the PM's
    signal to edit the prompt, not something to silently cut.

    The strip repeats until the string stops changing, because the wrappings
    nest: « - « Phrase. » » puts a dash outside a quote, and one fixed
    quotes-then-dash pass would leave the opening guillemet behind.
    """
    text = " ".join(str(raw or "").split())
    previous = None
    while text != previous:
        previous = text
        text = text.strip("«»\"“” ").lstrip("-–—").strip()
    return text


def _profile_fields(user_id: str) -> dict:
    """The four Profil de base fields, lifted off the ORM before the stream."""
    profile = Profile.query.filter_by(user_id=user_id).first()
    return {
        "prenom": profile.prenom if profile else None,
        "tranche_age": profile.tranche_age if profile else None,
        "situation": profile.situation if profile else None,
        "projet": profile.projet if profile else None,
    }


# ── the S0 phrase ────────────────────────────────────────────────────────────


def _fail_micro(voyage: Voyage, message: str) -> None:
    """Record the failure inside the ciphertext; only the status is plaintext."""
    voyage.micro = {**(voyage.micro or {}), "error": str(message)[:ERROR_MAX_CHARS]}
    voyage.micro_status = "error"
    db.session.commit()


EMPTY_PHRASE_ERROR = "Le modèle n'a renvoyé aucune phrase lisible."


def _generate_phrase(model: str, system_prompt: str,
                     messages: list) -> tuple[str, str | None, int, int]:
    """Both of the phrase's calls: the first, and at most one corrective turn.

    Returns (phrase, failure, tokens_in, tokens_out) — exactly one of phrase
    and failure is non-empty. Pure with respect to the database: the caller
    runs it with no connection held and writes the outcome back afterwards.
    The first call's exception propagates; the caller records it.

    The portrait keeps a draft that still leaks and flags it, because a
    counselor edits it before the person reads a word. Nobody stands between
    this phrase and the person, so a sentence that still leaks after the
    correction — or whose correction never answered — is refused outright
    and never leaves this function. « Réessayer » on the hub is the way back.
    """
    raw, tokens_in, tokens_out = _stream_text(model, system_prompt, messages,
                                              MICRO_MAX_TOKENS, None)
    tokens_in, tokens_out = tokens_in or 0, tokens_out or 0

    phrase = _one_sentence(raw)
    if not phrase:
        return "", EMPTY_PHRASE_ERROR, tokens_in, tokens_out

    leaks = leak_check({"phrase": phrase})
    if not leaks:
        return phrase, None, tokens_in, tokens_out

    retry = messages + [
        {"role": "assistant", "content": phrase},
        {"role": "user", "content": _micro_leak_retry_message(leaks)},
    ]
    try:
        raw, t_in, t_out = _stream_text(model, system_prompt, retry, MICRO_MAX_TOKENS, None)
    except Exception as exc:        # noqa: BLE001 — becomes the row's error
        return "", str(exc), tokens_in, tokens_out
    tokens_in += t_in or 0
    tokens_out += t_out or 0

    phrase = _one_sentence(raw)
    if not phrase:
        return "", EMPTY_PHRASE_ERROR, tokens_in, tokens_out
    still = leak_check({"phrase": phrase})
    if still:
        return ("", "Vocabulaire interdit dans la phrase : " + ", ".join(still) + ".",
                tokens_in, tokens_out)
    return phrase, None, tokens_in, tokens_out


def _run_micro(voyage_id: str, app) -> None:
    """Write the session-0 phrase onto the voyage row.

    Runs inside a background daemon thread spawned by
    POST /api/voyage/sessions/0/complete. No progress reporter: the hub polls
    GET /api/voyage every 2 s while micro_status == "generating", and the free
    model answers in a few seconds.
    """
    with app.app_context():
        voyage = db.session.get(Voyage, voyage_id)
        if not voyage:
            return

        prompt = PromptVersion.query.filter_by(is_active=True, path=MICRO_SLOT).first()
        if not prompt:
            _fail_micro(voyage, f"Aucun prompt actif pour le slot {MICRO_SLOT}.")
            return

        # Everything the call needs, captured as plain values BEFORE the
        # connection is released.
        try:
            system_prompt = prompt.system_prompt_text
            prompt_version_id = prompt.id
            user_message = _micro_user_message(
                voyage.synthesis(), _profile_fields(voyage.user_id).get("prenom"))
            model, _ = tiers.model_for(tiers.FREE)
        except Exception as exc:            # noqa: BLE001 — recorded on the row
            # The route already set micro_status = "generating" and committed, so a
            # build that raises here would strand the row there for ever: this thread
            # is the only thing that will ever move it.
            _fail_micro(voyage, str(exc))
            return

        # prompt_version_id is written now rather than only in the success
        # payload, so a run that fails still names the prompt that produced the
        # failure (B2G traceability). _fail_micro merges onto this dict.
        voyage.micro = {**(voyage.micro or {}), "prompt_version_id": prompt_version_id}
        voyage.micro_status = "generating"
        db.session.commit()

        # Release the pooled connection for the duration of the call: holding
        # one across the stream lets the DB drop it as idle, and the final
        # commit then fails with "Lost connection" on a row stuck 'generating'.
        db.session.remove()

        try:
            phrase, failure, tokens_in, tokens_out = _generate_phrase(
                model, system_prompt, [{"role": "user", "content": user_message}])
        except Exception as exc:            # noqa: BLE001 — recorded on the row
            # The stream ran with no connection held, so whatever session is in
            # the registry may be stale. remove() forces a fresh, pre-pinged
            # checkout; without it this get() is the statement that raises on a
            # dead connection, and the row strands in "generating" for ever.
            db.session.remove()
            voyage = db.session.get(Voyage, voyage_id)
            if voyage is not None:
                _fail_micro(voyage, str(exc))
            return

        # Fresh, pre-pinged connection to write the result — same reason as the
        # error path above: this write-back must not inherit a session the
        # stream left behind.
        db.session.remove()
        voyage = db.session.get(Voyage, voyage_id)
        if voyage is None:
            return

        # Every call that returned was paid for, whether or not it produced a
        # phrase worth keeping, so a refusal is billed like a success.
        voyage.tokens_in = (voyage.tokens_in or 0) + tokens_in
        voyage.tokens_out = (voyage.tokens_out or 0) + tokens_out

        # An empty phrase is a failure, not a success. micro_phrase would read
        # back as None while micro_status said "success", and Voyage.for_prompt
        # selects on that status — it would hand this voyage to an analysis as
        # the S0-phrase carrier with no phrase in it. portrait_sections takes
        # the same convention one property up: incomplete means empty. A
        # refused phrase takes the same path, and only the words it leaked
        # reach the payload — never the sentence.
        if failure:
            _fail_micro(voyage, failure)
            return

        voyage.micro = {
            "phrase": phrase,
            "prompt_version_id": prompt_version_id,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "error": None,
        }
        voyage.micro_status = "success"
        db.session.commit()


def start_micro(voyage_id: str, app) -> None:
    """Spawn a daemon thread that writes the session-0 phrase. Returns at once."""
    threading.Thread(target=_run_micro, args=(voyage_id, app), daemon=True).start()


# ── the portrait ─────────────────────────────────────────────────────────────


def _parse_sections(raw: str) -> dict[str, str]:
    """The six sections out of the model's answer.

    Structured output makes this a plain JSON object; the degraded path
    (extra_body refused) can return a fenced block or prose, so the same
    extract-then-repair ladder the analysis parser uses runs here too. Missing
    keys come back as empty strings rather than absent, so the counselor editor
    always has its six boxes.

    The repair rung is not decoration. Six prose sections against a 3000-token
    cap makes truncation the realistic failure, and a payload cut off mid-string
    is unparseable by json.loads but still holds every section that arrived —
    repair_json is what turns it into a mostly-complete draft a counselor can
    finish, instead of an "error" row that throws the finished sections away.
    """
    candidate = _extract_json_candidate(str(raw or ""))
    parsed = None
    for text in (candidate, repair_json(candidate)):
        try:
            value = json.loads(text)
        except (json.JSONDecodeError, ValueError, TypeError):
            continue
        if isinstance(value, dict):
            parsed = value
            break
    parsed = parsed or {}
    return {key: str(parsed.get(key) or "").strip() for key in PORTRAIT_KEYS}


def _leak_retry_message(leaks: list) -> str:
    """The corrective turn, in French — the whole exchange is in French."""
    return (
        "Ce texte contient des mots interdits : " + ", ".join(leaks) + ". "
        "Réécris le portrait en entier sans ces mots et sans aucun autre terme "
        "technique de psychologie ou de ressources humaines. Garde les six mêmes "
        "sections, le même fond et la même longueur. Réponds uniquement avec le "
        "JSON des six sections."
    )


def _micro_leak_retry_message(leaks: list) -> str:
    """The session-0 phrase's corrective turn, in French like the portrait's.
    The word range is MICRO_WORDS, the counselor manual's rule."""
    low, high = MICRO_WORDS
    return (
        "Cette phrase contient des mots interdits : " + ", ".join(leaks) + ". "
        "Réécris-la sans ces mots et sans aucun autre terme technique de "
        "psychologie ou de ressources humaines. Une seule phrase, "
        f"de {low} à {high} mots. Réponds uniquement avec la phrase."
    )


def _fail_portrait(voyage: Voyage, message: str) -> None:
    """Record the failure inside the ciphertext; only the status is plaintext."""
    voyage.portrait = {**(voyage.portrait or {}), "error": str(message)[:ERROR_MAX_CHARS]}
    voyage.portrait_status = "error"
    db.session.commit()


def _run_portrait(voyage_id: str, app) -> None:
    """Draft the six-section portrait onto the voyage row.

    Runs inside a background daemon thread spawned by
    POST /api/voyage/sessions/5/complete, or by the counselor's regenerate.
    The result is a DRAFT: a counselor edits and validates it before the person
    can read a word of it.
    """
    with app.app_context():
        voyage = db.session.get(Voyage, voyage_id)
        if not voyage:
            return

        prompt = PromptVersion.query.filter_by(is_active=True, path=PORTRAIT_SLOT).first()
        if not prompt:
            _fail_portrait(voyage, f"Aucun prompt actif pour le slot {PORTRAIT_SLOT}.")
            return

        # Everything the call needs, captured as plain values BEFORE the
        # connection is released.
        try:
            system_prompt = prompt.system_prompt_text
            prompt_version_id = prompt.id
            synthesis = voyage.synthesis()
            user_message = _portrait_user_message(
                synthesis, voyage.responses, _profile_fields(voyage.user_id))
            schema = _portrait_schema()
            model, _ = tiers.model_for(tiers.PAID)
        except Exception as exc:            # noqa: BLE001 — recorded on the row
            # The route already set portrait_status = "generating" and committed, so
            # a build that raises here would strand the row there for ever: this
            # thread is the only thing that will ever move it.
            _fail_portrait(voyage, str(exc))
            return

        # prompt_version_id is written now rather than only in the success
        # payload, so a run that fails still names the prompt that produced the
        # failure (B2G traceability). _fail_portrait merges onto this dict.
        voyage.portrait = {**(voyage.portrait or {}), "prompt_version_id": prompt_version_id}
        voyage.portrait_status = "generating"
        db.session.commit()

        # Release the pooled connection for the duration of the call: holding
        # one across the stream lets the DB drop it as idle, and the final
        # commit then fails with "Lost connection" on a row stuck 'generating'.
        db.session.remove()

        messages = [{"role": "user", "content": user_message}]
        tokens_in = tokens_out = 0
        flags: list[str] = []
        try:
            raw, t_in, t_out = _stream_text(model, system_prompt, messages,
                                            PORTRAIT_MAX_TOKENS, schema)
            tokens_in += t_in or 0
            tokens_out += t_out or 0
            sections = _parse_sections(raw)

            leaks = leak_check(sections)
            if leaks:
                # One corrective turn quoting the offending words. Whatever
                # comes back is what we keep: still leaking means flagged, not
                # discarded — the counselor sees a banner and fixes the wording
                # in the editor.
                retry = messages + [
                    {"role": "assistant",
                     "content": json.dumps(sections, ensure_ascii=False)},
                    {"role": "user", "content": _leak_retry_message(leaks)},
                ]
                try:
                    raw, t_in, t_out = _stream_text(model, system_prompt, retry,
                                                    PORTRAIT_MAX_TOKENS, schema)
                except Exception:       # noqa: BLE001 — the first draft still stands
                    # The retry is an improvement, not a precondition. Losing it
                    # costs the wording, not the portrait: keep the leaking draft
                    # and flag it, exactly as we would if the retry had returned
                    # and still leaked. Letting this reach the outer handler
                    # would send a usable draft to "error" over a timeout.
                    flags = [FLAG_VOCABULAIRE]
                else:
                    tokens_in += t_in or 0
                    tokens_out += t_out or 0
                    sections = _parse_sections(raw)
                    if leak_check(sections):
                        flags = [FLAG_VOCABULAIRE]
        except Exception as exc:            # noqa: BLE001 — recorded on the row
            # The stream ran with no connection held, so whatever session is in
            # the registry may be stale. remove() forces a fresh, pre-pinged
            # checkout; without it this get() is the statement that raises on a
            # dead connection, and the row strands in "generating" for ever.
            db.session.remove()
            voyage = db.session.get(Voyage, voyage_id)
            if voyage is not None:
                _fail_portrait(voyage, str(exc))
            return

        # Fresh, pre-pinged connection to write the result — same reason as the
        # error path above: this write-back must not inherit a session the
        # stream left behind.
        db.session.remove()
        voyage = db.session.get(Voyage, voyage_id)
        if voyage is None:
            return

        # Six empty sections are a failure, not a success. portrait_status
        # "draft" is what puts this row in the counselor's validation queue, and
        # portrait_sections would read back as {} — the counselor would open an
        # empty editor with no clue why. Same convention as the micro's phrase.
        if not any(sections.values()):
            _fail_portrait(voyage, "Le modèle n'a renvoyé aucune section lisible.")
            return

        voyage.portrait = {
            "sections": sections,
            # The synthesis the portrait was written from, kept so a later
            # scoring correction can never make an existing portrait a lie.
            "snapshot": synthesis,
            "flags": flags,
            "edited": False,
            "prompt_version_id": prompt_version_id,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "error": None,
        }
        voyage.portrait_status = "draft"
        voyage.tokens_in = (voyage.tokens_in or 0) + tokens_in
        voyage.tokens_out = (voyage.tokens_out or 0) + tokens_out
        db.session.commit()


def start_portrait(voyage_id: str, app) -> None:
    """Spawn a daemon thread that drafts the portrait. Returns at once."""
    threading.Thread(target=_run_portrait, args=(voyage_id, app), daemon=True).start()
