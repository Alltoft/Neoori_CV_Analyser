"""The one-off purge of parcours 2 and 3 (spec 2026-10-08, « Data purge »).

Temporary, like the script itself: both are removed once production is purged.
"""
import pytest

import purge_retired_parcours as purge_mod
from app.extensions import db
from app.models.analysis import Analysis
from app.models.code_redemption import CodeRedemption
from app.models.counselor_code import CounselorCode
from app.models.counselor_note import CounselorNote
from app.models.price_feedback import PriceFeedback
from app.models.prompt_version import PromptVersion
from app.models.user import User


def _prompt(path, label, active=True):
    p = PromptVersion(version_label=label, system_prompt_text="x", path=path, is_active=active)
    db.session.add(p)
    db.session.commit()
    return p


def _analysis(inputs, status="success", prompt=None, unlock_method=None):
    a = Analysis(inputs=inputs, status=status, unlock_method=unlock_method,
                 prompt_version_id=prompt.id if prompt else None)
    db.session.add(a)
    db.session.commit()
    return a


def _silent(_line):
    pass


@pytest.fixture
def world(app):
    """Parcours 1 rows in every shape the old code read as parcours 1, retired
    rows in every shape it read as parcours 2 or 3, and what hangs off them."""
    counselor = User(email="conseil@test.fr", password_hash="x", role="counselor")
    db.session.add(counselor)
    db.session.commit()

    p1 = _prompt("1", "v1.8")
    micro = _prompt("voyage_micro", "v1.0-VM")
    p2 = _prompt("2", "v1.1-P2")
    p3 = _prompt("3", "v1.1-P3")
    p3_old = _prompt("3", "v1.0-B", active=False)
    legacy_b = _prompt("B", "v0.9-B", active=False)  # defensive: migrated to "3" long ago

    kept = [
        _analysis({"_path": "1", "cv_text": "x"}, prompt=p1),
        _analysis({"_path": "A", "cv_text": "x"}, prompt=p1),
        _analysis({"cv_text": "x"}, prompt=p1),            # no _path at all
        _analysis({"_path": " 2", "cv_text": "x"}),         # the old normalize()
        _analysis({"_path": 2, "cv_text": "x"}),            # read these three
        _analysis({"_path": ["2"], "cv_text": "x"}),        # as parcours 1
        _analysis(None, status="draft"),
    ]
    retired = [
        _analysis({"_path": "2", "cv_text": "x"}, prompt=p2, unlock_method="payment"),
        _analysis({"_path": "3", "experiences": "x"}, prompt=p3),
        _analysis({"_path": "B", "aime": ["x"]}, prompt=p3_old),
        _analysis({"_path": "b"}, status="draft"),
    ]

    db.session.add(CounselorNote(analysis_id=retired[0].id, counselor_id=counselor.id, body="n"))
    db.session.add(CounselorNote(analysis_id=kept[0].id, counselor_id=counselor.id, body="n"))
    db.session.add(PriceFeedback(analysis_id=retired[1].id, bucket="5_10"))
    db.session.add(PriceFeedback(analysis_id=kept[0].id, bucket="5_10"))
    code = CounselorCode(label="Cap Emploi test")
    db.session.add(code)
    db.session.commit()
    db.session.add(CodeRedemption(code_id=code.id, target_type="analysis",
                                  target_id=retired[0].id))
    db.session.commit()

    return {
        "kept": [a.id for a in kept],
        "retired": [a.id for a in retired],
        "kept_prompts": {p1.id, micro.id},
        "retired_prompts": {p2.id, p3.id, p3_old.id, legacy_b.id},
        "counselor": counselor.id,
    }


def test_retired_kind_mirrors_the_old_normalize():
    """Review Focus 5: exactly what the old normalize() sent to parcours 2/3."""
    assert purge_mod.retired_kind("2") == "2"
    assert purge_mod.retired_kind("3") == "3"
    assert purge_mod.retired_kind("B") == "B"
    assert purge_mod.retired_kind("b") == "B"
    for kept in ("1", "A", None, " 2", "2 ", 2, 3, ["2"], {"x": 1}, "", "nonsense"):
        assert purge_mod.retired_kind(kept) is None, kept


def test_the_dry_run_changes_nothing(world):
    lines = []
    census = purge_mod.purge(apply=False, out=lines.append)

    assert sorted(census.analysis_ids) == sorted(world["retired"])
    assert census.by_kind == {("2", "success"): 1, ("3", "success"): 1,
                              ("B", "success"): 1, ("B", "draft"): 1}
    assert census.unlocked == 1
    assert census.notes == 1
    assert census.feedback == 1
    assert census.redemptions_kept == 1
    assert {p.id for p in census.prompts} == world["retired_prompts"]
    assert census.blocking == 0

    assert Analysis.query.count() == len(world["kept"]) + len(world["retired"])
    assert CounselorNote.query.count() == 2
    assert PriceFeedback.query.count() == 2
    assert PromptVersion.query.count() == 6
    assert any("--apply" in line for line in lines)


def test_apply_deletes_exactly_the_retired_rows(world):
    after = purge_mod.purge(apply=True, out=_silent)

    assert {a.id for a in Analysis.query.all()} == set(world["kept"])
    assert {n.analysis_id for n in CounselorNote.query.all()} == {world["kept"][0]}
    assert {f.analysis_id for f in PriceFeedback.query.all()} == {world["kept"][0]}
    assert {p.id for p in PromptVersion.query.all()} == world["kept_prompts"]
    # Kept on purpose (spec, decision 5).
    assert CodeRedemption.query.count() == 1
    assert db.session.get(User, world["counselor"]) is not None
    # The census taken after the run finds nothing left.
    assert after.analysis_ids == []
    assert after.prompts == []


def test_a_second_run_deletes_nothing(world):
    purge_mod.purge(apply=True, out=_silent)
    second = purge_mod.purge(apply=True, out=_silent)
    assert second.analysis_ids == []
    assert second.prompts == []
    assert Analysis.query.count() == len(world["kept"])


def test_a_kept_analysis_on_a_retired_prompt_aborts_everything(world):
    """Review Focus 4: inconsistent data stops the run before anything goes —
    never half a purge."""
    p2 = PromptVersion.query.filter_by(path="2").one()
    _analysis({"_path": "1", "cv_text": "x"}, prompt=p2)
    before = Analysis.query.count()

    with pytest.raises(purge_mod.PurgeAborted):
        purge_mod.purge(apply=True, out=_silent)

    assert Analysis.query.count() == before
    assert PromptVersion.query.count() == 6
    assert CounselorNote.query.count() == 2
    assert PriceFeedback.query.count() == 2
