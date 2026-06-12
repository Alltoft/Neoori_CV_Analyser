"""
Re-parse stored analyses whose output collapsed into a single §1 blob.

Older analyses generated while the active prompt returned markdown (no JSON
envelope) were stored via the last-resort parser fallback:
    {"1": {"title": "Analyse", "body_markdown": "<entire response>", ...}}

The parser now splits markdown §N headings into proper sections. This script
re-runs the parser on the preserved raw_output and updates the stored output.
Idempotent: rows that don't match the fallback shape are skipped.

Run from /backend:  python reparse_outputs.py
"""
from app import create_app
from app.extensions import db
from app.models.analysis import Analysis
from app.services.anthropic_service import _parse_output

app = create_app()
with app.app_context():
    candidates = Analysis.query.filter_by(status="success").all()
    fixed = skipped = 0
    for a in candidates:
        out = a.output or {}
        is_fallback_blob = (
            list(out.keys()) == ["1"]
            and isinstance(out.get("1"), dict)
            and out["1"].get("title") == "Analyse"
        )
        if not is_fallback_blob or not (a.raw_output or "").strip():
            skipped += 1
            continue
        reparsed = _parse_output(a.raw_output)
        if len(reparsed) > 1:
            a.output = reparsed
            fixed += 1
        else:
            skipped += 1
    db.session.commit()
    print(f"Re-parsed {fixed} analysis/analyses, skipped {skipped}.")
