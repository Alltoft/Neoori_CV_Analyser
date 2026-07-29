"""Plan tiers: which model runs, how big the budget is, what it costs.

One table, so the generation path and the cost dashboard can't drift apart.
Before CDC v1.2 the tier was stored as a model nickname ("haiku"/"sonnet")
inside the Analysis.inputs JSON blob; it is now a plan name on a real column.
LEGACY maps the old values for rows written before that migration.
"""
import os

FREE = "free"
PAID = "paid"
PREMIUM = "premium"

TIERS = (FREE, PAID, PREMIUM)

# Prices are Anthropic list rates per million tokens, 2026-07.
# Sonnet 5 has promotional pricing ($2/$10) through 2026-08-31; list price is
# used here so the dashboard never under-reports what a month will cost.
TIER_CONFIG = {
    FREE: {
        "env": "MODEL_FREE",
        "model": "claude-haiku-4-5",
        "max_tokens": 8000,
        "usd_in": 1.00,
        "usd_out": 5.00,
        "label": "Gratuit",
    },
    PAID: {
        "env": "MODEL_PAID",
        "model": "claude-sonnet-5",
        "max_tokens": 8000,
        "usd_in": 3.00,
        "usd_out": 15.00,
        "label": "Payant",
    },
    PREMIUM: {
        "env": "MODEL_PREMIUM",
        "model": "claude-opus-5",
        # Opus 5 thinks by default and thinking counts against max_tokens, so
        # the premium budget has to cover reasoning *and* an 11-section report.
        # 8000 truncates mid-report.
        "max_tokens": 20000,
        "usd_in": 5.00,
        "usd_out": 25.00,
        "label": "Premium",
    },
}

USD_TO_EUR = 0.92

# Model nicknames written before the plan-name migration.
LEGACY = {"haiku": FREE, "sonnet": PAID, "opus": PREMIUM}


def normalize(tier) -> str:
    """Coerce a stored or client-supplied tier to a plan name."""
    value = (tier or "").strip().lower()
    if value in TIER_CONFIG:
        return value
    return LEGACY.get(value, FREE)


def model_for(tier: str) -> tuple[str, int]:
    """(model id, max_tokens) for a tier. Env vars override the model id."""
    cfg = TIER_CONFIG[normalize(tier)]
    model = os.getenv(cfg["env"]) or cfg["model"]
    # Historical: model ids were once carried with a LiteLLM-style prefix.
    return model.removeprefix("anthropic/"), cfg["max_tokens"]


def pricing() -> dict:
    """Per-tier rates, for the admin cost dashboard."""
    return {
        t: {
            "label": c["label"],
            "model": os.getenv(c["env"]) or c["model"],
            "usd_in": c["usd_in"],
            "usd_out": c["usd_out"],
        }
        for t, c in TIER_CONFIG.items()
    }


def cost_usd(tier: str, tokens_in: int, tokens_out: int) -> float:
    cfg = TIER_CONFIG[normalize(tier)]
    return (tokens_in * cfg["usd_in"] + tokens_out * cfg["usd_out"]) / 1_000_000
