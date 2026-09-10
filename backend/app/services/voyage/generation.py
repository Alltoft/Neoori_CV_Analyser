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
