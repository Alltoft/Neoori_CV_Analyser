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
    the person must never read, retries once with a corrective turn, then keeps
    the draft and flags it for the counselor.

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
