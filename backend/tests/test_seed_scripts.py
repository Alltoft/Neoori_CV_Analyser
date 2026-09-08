"""Guards the parcours id the seed scripts write into PromptVersion.path.

CDC v1.2 replaced the A/B path codes with parcours ids, and the analysis
lookup filters on that column directly. A stale literal here seeds a prompt
no analysis can ever find — the run fails instantly with "Aucun prompt actif
pour le chemin 1", which is what happened on the VPS after a fresh seed.
"""
import re
from pathlib import Path

from app.services import section_registry as registry

# seed script → the parcours its prompt belongs to
SEEDS = {
    "seed_prompt_v18.py": "1",     # ex-path A, « J'ai une cible »
    "seed_prompt_v11_p3.py": "3",  # ex-path B, « Je pars de zéro »
    "seed_prompt_v10_p2.py": "2",  # authored after the migration, no legacy code
}

_LITERAL = re.compile(r"""(?:path\s*=|^PATH\s*=)\s*["'](\w)["']""", re.MULTILINE)


def test_seed_scripts_write_parcours_ids():
    backend_root = Path(__file__).resolve().parents[1]
    for name, expected in SEEDS.items():
        source = (backend_root / name).read_text(encoding="utf-8")
        literals = set(_LITERAL.findall(source))
        assert literals, f"{name}: no path literal found"
        for value in literals:
            assert registry.is_valid(value), (
                f"{name}: path={value!r} is not a parcours id "
                f"({sorted(registry.PARCOURS)})"
            )
            assert value == expected, f"{name}: expected path {expected!r}, found {value!r}"
