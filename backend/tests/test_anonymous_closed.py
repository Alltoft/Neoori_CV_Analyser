"""No analysis and no upload without an account (email verification spec,
decision 13). The anonymous path is what made throwaway accounts
unnecessary: nobody needs a fake account when no account is needed."""
import io
from unittest.mock import patch

import pytest

# A payload create_analysis accepts once signed in: chemin A (the default) asks
# for a target of at least 50 characters.
P1 = {"inputs": {
    "_path": "1",
    "cv_text": "c" * 300,
    "cible_visee": "Chauffeur livreur PL dans une entreprise de transport régional",
}}


@pytest.mark.parametrize("path", ["/api/upload/cv", "/api/upload/projet"])
def test_an_upload_needs_an_account(client, path):
    data = {"file": (io.BytesIO(b"%PDF-1.4"), "cv.pdf", "application/pdf")}
    res = client.post(path, data=data, content_type="multipart/form-data")
    assert res.status_code == 401


def test_an_analysis_needs_an_account(client):
    assert client.post("/api/analyses/", json=P1).status_code == 401


def test_a_draft_needs_an_account(client):
    # Already jwt_required before this change; pinned here so the closed
    # surface (create, drafts, both uploads) is asserted in one place.
    assert client.post("/api/analyses/draft", json=P1).status_code == 401


@patch("app.routes.analyses.start_analysis")
def test_a_signed_in_candidate_still_creates_one(_start, client, candidate_headers):
    res = client.post("/api/analyses/", json=P1, headers=candidate_headers)
    assert res.status_code == 201, res.data
