# Le voyage — phase 0 handoff

Phase 0 (question bank + scoring engine) is complete and merged into `initial` locally.
24 commits, 232 tests, 0 deselected. Nothing is pushed; nothing is deployed.

**Spec:** `docs/superpowers/specs/2026-09-09-voyage-design.md`
**Interface contract:** `docs/superpowers/plans/2026-09-09-voyage-contracts.md` (§A bank, §B scoring)
**Plans for phases 1–5:** `docs/superpowers/plans/2026-09-09-voyage-phase-{1..5}-*.md`

## What exists

| File | Contents |
|---|---|
| `backend/app/services/voyage/bank.py` | 6 sessions, 53 scored items (French verbatim from the paper cahier), 10 bipolar axes, scoring weights, accessors, `public()` |
| `backend/app/services/voyage/scoring.py` | 5 scorers, `synthesize()`, `prompt_context()`, helpers `_dominant`/`_level`/`_line` |
| `backend/tests/test_voyage_bank.py` · `test_voyage_scoring.py` | 84 tests |

`bank.py` imports **nothing**; `scoring.py` imports only `from . import bank`. Both must stay that way — phase 1 calls this package inside a request and phase 2 from a background thread, with no Flask app context.

## Decisions a future reader will otherwise trip over

- **Three errata in the source paper manual, implemented deliberately.** An axis loaded by a single item is excluded from being flagged as an ambivalence (A1 has one item, so it sits inside the band for every person alive). RIASEC maxima are **computed** — R12 I11 A10 S10 E11 C9 — not the manual's printed E10/C10, which are transcription slips. Big Five levels use ±2 where the manual gives no threshold.
- **Cahier text is verbatim even where it crosses the CLAUDE.md copy ban list.** Six instances in `bank.py` (`épanouirais`, `te révéler` ×2, `s'épanouissent`, `te révèles`, `révélé`). Session content is quoted material the PM wrote and paper-tested; paraphrasing a question mid-instrument changes what it measures. The ban list still binds every string the app authors. **Open: the PM may overrule this.**
- **« tu jonglles » at S3-7 D is a typo in the source, transcribed as-is.**
- **`conservation` and `integrite` are not canonical Schwartz values.** They are the manual's own vocabulary, and the counselor's sheet must match the paper it replaces.
- **`item()` / `option()` return `None`; `session()` / `axis()` raise `KeyError`.** Deliberate: the first pair take ids arriving over HTTP where unknown means bad input (a 400); the second take ids from our own code where unknown means a bug.
- **`score_s0`'s zero-resultant filter is unreachable today** — axis resultants carry the parity of their item count and A1/A2/A6 are odd, so at least three axes are always non-zero. Kept as cheap insurance if the PM ever adds session-0 items and changes a parity.

## What phase 1 must know

- **`oui`/`non` are raw check counts, not points for and against.** With only the reversed item S0-11 checked, A5 reports `{oui: 1, non: 3, resultant: -4}` — one OUI *and* the most negative resultant the axis can produce. Faithful to the paper grid, but the counselor UI must not render the three as a sum or the sheet looks arithmetically broken.
- **A bank edit silently un-scores old voyages.** `missing_items` treats an answer that no longer validates as missing, so removing an option letter turns a completed session incomplete, `score_*` returns `None`, and a *validated* voyage's `prompt_context` quietly drops six of its nine lines. Compare `voyage.scoring_version` against `bank.SCORING_VERSION` and surface a warning rather than an empty sheet.
- **`missing_items` / `session_complete` / `completeness` raise `KeyError` on an unknown session id** (via `bank.session`). Validate `n` at the route.
- **`_answers()` fail-softs on a malformed payload.** A route that forgets to wrap `{"answers": ..., "billets": ...}` gets every item reported missing rather than an error — the person sees 0% complete with their answers discarded. Guard the shape at the route boundary.
- **The no-digit property covers the scoring path only.** `micro_phrase` is model-generated and passes through untouched, so "17 ans" is a legitimate digit in the block. Do not add a runtime assertion in phase 5 that would 500 on it.
- **`*_dominant` can be a list of two or three, by design.** `Besoin dominant : autonomie, appartenance, competence` is legal output; treat "all tied" as "no dominant need" rather than reading element zero.
- **Live references:** `sessions()`, `session()`, `items()`, `option()`, `chosen_option()` all return objects inside `bank.SESSIONS`. Only `public()` deep-copies. Docstrings now say so.
- **Test-file location differs from the contract manifest.** The contract names `test_voyage_prompt_context.py`; phase 0's prompt-context tests live at the bottom of `test_voyage_scoring.py`. Phase 5 should extend rather than re-create, or the digit/leak assertions end up duplicated in two files that drift.

## Open, needing the PM

1. **`Besoin dominant : competence` reaches the model unaccented.** `sdt_dominant` emits raw ASCII tags; `autonomie` and `appartenance` are coincidentally correct French, `competence` is not. Fixing it needs a contract amendment to §H — either an `SDT_PLAIN` map beside `STYLE_PLAIN`, or the PM accepts the token. Decide before phase 5 wires it.
2. **Ban list vs cahier** — see above.
3. **Intro inconsistency:** sessions 0/1/2 end their intro with an instruction line ("7 scènes. Dans chacune, entoure la lettre…"); 3/4/5 do not. Invisible now, visible in phase 3's session player.
4. **`« te attribuer »` should elide to `t'attribuer`** (S5-5 option A `plain`). Model-facing, low impact, same copy pass.

## Deliberately not done

Nine minor findings were triaged "can wait" by the final review: STYLE_PLAIN values unasserted (phase 2 pins them), three stray mid-file `import` sites, the two copy items above, a fail-soft contract test, two comment/naming nits, and upgrading `test_synthesize_is_pure`'s one-field bank canary to a deepcopy snapshot. Thirteen more were dropped as cosmetic or already covered.
