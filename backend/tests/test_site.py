"""DOMAIN, the one setting, and what is built from it (subdomain split spec,
decisions 19–20, 26 and 31)."""
import pytest

from app.config import _domain
from app.utils import site


@pytest.fixture
def neoori(app):
    app.config.update(DOMAIN="neoori.tech", PUBLIC_SCHEME="https", PUBLIC_PORT="")
    return app


@pytest.mark.parametrize("raw, expected", [
    ("neoori.tech", "neoori.tech"),
    (" Neoori.Tech. ", "neoori.tech"),
    ("", "localhost"),
    ("   ", "localhost"),
])
def test_domain_is_read_trimmed_and_lowercased(raw, expected):
    assert _domain(raw) == expected


def test_the_tests_run_on_a_single_label_domain(app):
    assert app.config["DOMAIN"] == "localhost"
    assert app.config["PUBLIC_SCHEME"] == "https"
    assert app.config["PUBLIC_PORT"] == ""


def test_the_three_origins_come_from_domain(neoori):
    assert site.origin("root") == "https://neoori.tech"
    assert site.origin("cv") == "https://cv.neoori.tech"
    assert site.origin("voyage") == "https://voyage.neoori.tech"
    assert site.origins() == [
        "https://neoori.tech", "https://cv.neoori.tech", "https://voyage.neoori.tech",
    ]


def test_dev_adds_its_scheme_and_port(app):
    app.config.update(DOMAIN="neoori.localhost", PUBLIC_SCHEME="http", PUBLIC_PORT="8080")
    assert site.origin("cv") == "http://cv.neoori.localhost:8080"


def test_an_explicit_config_needs_no_app_context():
    config = {"DOMAIN": "example.fr", "PUBLIC_SCHEME": "https", "PUBLIC_PORT": ""}
    assert site.origins(config) == [
        "https://example.fr", "https://cv.example.fr", "https://voyage.example.fr",
    ]


@pytest.mark.parametrize("host, expected", [
    ("neoori.tech", "root"),
    ("cv.neoori.tech", "cv"),
    ("voyage.neoori.tech", "voyage"),
    ("CV.Neoori.Tech", "cv"),
    ("cv.neoori.tech:8080", "cv"),
    ("voyage.neoori.tech.", "voyage"),
    ("www.neoori.tech", None),
    ("attacker.example", None),
    ("cv.neoori.tech.evil.example", None),
    ("cv.neoori.techx", None),
    ("x@cv.neoori.tech", None),
    ("186.240.157.26", None),
    ("[::1]:5000", None),
    ("", None),
    (None, None),
])
def test_which_app_a_host_is(host, expected):
    assert site.app_of_host(host, "neoori.tech") == expected


def test_outside_a_request_there_is_no_app_and_the_origin_is_cv(neoori):
    assert site.request_app() is None
    assert site.request_origin() == "https://cv.neoori.tech"


@pytest.mark.parametrize("host, expected", [
    ("cv.neoori.tech", "https://cv.neoori.tech"),
    ("voyage.neoori.tech", "https://voyage.neoori.tech"),
    ("Voyage.Neoori.Tech:8080", "https://voyage.neoori.tech"),
    ("neoori.tech", "https://cv.neoori.tech"),
    ("attacker.example", "https://cv.neoori.tech"),
])
def test_the_requesting_origin_is_cv_or_voyage_never_the_host_itself(neoori, host, expected):
    with neoori.test_request_context("/", base_url=f"http://{host}"):
        assert site.request_origin() == expected


@pytest.mark.parametrize("domain, expected", [
    ("neoori.tech", "neoori.tech"),
    ("neoori.localhost", "neoori.localhost"),
    ("localhost", None),
])
def test_the_cookie_domain(domain, expected):
    assert site.cookie_domain(domain) == expected
