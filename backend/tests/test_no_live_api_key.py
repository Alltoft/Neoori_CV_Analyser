"""The suite must not be able to bill the real Anthropic account.

conftest's autouse _no_live_anthropic_key fixture blanks the key, because
create_app() calls load_dotenv() and _get_client() reads the key at call time --
so a test that forgets to patch the client would otherwise make a real, paid
call and still pass green.

This file exists because the fixture was shipped unverified: with nothing
reading the key, deleting the fixture left the whole suite green. A guard no
test can miss the removal of is not a guard.
"""
import os

from app.services.anthropic_service import _get_client


def test_the_environment_key_is_blank_for_every_test():
    assert os.getenv("ANTHROPIC_API_KEY") == ""


def test_an_unpatched_client_carries_no_credential(app):
    """The SDK builds a client from an empty key and only rejects at request
    time, so this is what the guard actually buys: an unpatched call gets a 401
    instead of a billed completion."""
    assert _get_client().api_key == ""
