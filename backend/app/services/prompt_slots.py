"""Valid values for PromptVersion.path — parcours ids plus the voyage prompt slots.

Widened from String(1) to String(16) so the two voyage prompts do not have to
masquerade as parcours "4"/"5" everywhere the registry is iterated (spec 18).
A slot is what the generation path looks a prompt up by:

    PromptVersion.query.filter_by(is_active=True, path=<slot>)

so a wrong value here seeds a prompt nothing can ever find.
"""
from . import section_registry as registry

VOYAGE_MICRO = "voyage_micro"
VOYAGE_PORTRAIT = "voyage_portrait"
VOYAGE_SLOTS = (VOYAGE_MICRO, VOYAGE_PORTRAIT)

LABELS = {
    "1": "Parcours 1 · J'ai une cible",
    "2": "Parcours 2 · Je cherche ma direction",
    "3": "Parcours 3 · Je pars de zéro",
    VOYAGE_MICRO: "Voyage · phrase (S0)",
    VOYAGE_PORTRAIT: "Voyage · portrait",
}


def valid() -> tuple[str, ...]:
    """('1', '2', '3', 'voyage_micro', 'voyage_portrait') — parcours ids first."""
    return tuple(registry.PARCOURS) + VOYAGE_SLOTS


def is_valid(slot) -> bool:
    return slot in valid()


def is_voyage(slot) -> bool:
    return slot in VOYAGE_SLOTS


def normalize(slot) -> str:
    """Coerce a stored or client-supplied value to a slot.

    The voyage slots are matched *before* any .upper(): the admin route used to
    uppercase before validating, and "VOYAGE_MICRO" is not a slot. Anything
    else falls through to the registry, which still folds the legacy 'A'/'B'
    path codes onto parcours ids and defaults the unrecognised to parcours 1.
    """
    value = str(slot or "").strip()
    if not value:
        return registry.DEFAULT_PARCOURS
    if value.lower() in VOYAGE_SLOTS:
        return value.lower()
    return registry.normalize(value.upper())


def label(slot: str) -> str:
    """French label for the admin selector. Falls back to the raw id."""
    return LABELS.get(slot, slot)


def choices() -> list[dict]:
    """[{"value": "1", "label": "Parcours 1 · J'ai une cible"}, ...]."""
    return [{"value": slot, "label": label(slot)} for slot in valid()]
