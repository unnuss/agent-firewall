"""Credential loading, and the failure it is now designed to prevent (D-029).

These tests exist because of a real incident, not a hypothetical one. A stale exported
`OPENAI_API_KEY` — a different key from the one in `.env.local`, on an account with no
credit — silently won, and the resulting `credit_balance_exhausted` was written into
`EXPERIMENTS.md` as "blocked on billing" for a day. Every layer was reporting the truth
(`has_openai_key: true`) and none of it was the useful truth.

The property worth testing is therefore not "the right key wins" alone. It is that a
disagreement between the two sources **cannot be silent**, whichever way it is resolved.
"""

from __future__ import annotations

import os

import pytest

from agentfw.config import CredentialLoad, credential_report, fingerprint, load_local_env


@pytest.fixture
def env_file(tmp_path):
    def write(text: str):
        p = tmp_path / ".env.local"
        p.write_text(text, encoding="utf-8")
        return p

    return write


@pytest.fixture(autouse=True)
def clean_key(monkeypatch):
    monkeypatch.delenv("AGENTFW_TEST_KEY", raising=False)
    yield


def test_a_key_absent_from_the_environment_is_loaded(env_file, monkeypatch):
    path = env_file("AGENTFW_TEST_KEY=from-file\n")
    report = load_local_env(path)
    assert report.loaded == ["AGENTFW_TEST_KEY"]
    assert report.conflicts == []
    assert os.environ["AGENTFW_TEST_KEY"] == "from-file"
    monkeypatch.delenv("AGENTFW_TEST_KEY", raising=False)


def test_the_file_wins_a_conflict_and_says_so(env_file, monkeypatch):
    """The D-029 reversal. The old behaviour let the stale export win, in silence."""
    monkeypatch.setenv("AGENTFW_TEST_KEY", "stale-exported")
    path = env_file("AGENTFW_TEST_KEY=from-file\n")
    report = load_local_env(path)
    assert os.environ["AGENTFW_TEST_KEY"] == "from-file"
    assert report.conflicts == [("AGENTFW_TEST_KEY", ".env.local")]
    assert report.warnings(), "a shadowed credential must never be silent"
    assert "DIFFERENT" in report.warnings()[0]


def test_the_environment_can_still_win_but_not_quietly(env_file, monkeypatch):
    monkeypatch.setenv("AGENTFW_TEST_KEY", "exported")
    path = env_file("AGENTFW_TEST_KEY=from-file\n")
    report = load_local_env(path, prefer_environment=True)
    assert os.environ["AGENTFW_TEST_KEY"] == "exported"
    assert report.conflicts == [("AGENTFW_TEST_KEY", "the exported environment variable")]
    assert report.warnings()


def test_agreement_is_not_a_conflict(env_file, monkeypatch):
    monkeypatch.setenv("AGENTFW_TEST_KEY", "same")
    report = load_local_env(env_file("AGENTFW_TEST_KEY=same\n"))
    assert report.agreed == ["AGENTFW_TEST_KEY"]
    assert report.conflicts == []
    assert report.warnings() == []


def test_an_empty_exported_value_does_not_shadow(env_file, monkeypatch):
    """An exported-but-empty variable is the shape a half-finished shell profile leaves
    behind. Treating it as "set" would reintroduce the bug in its most confusing form."""
    monkeypatch.setenv("AGENTFW_TEST_KEY", "")
    report = load_local_env(env_file("AGENTFW_TEST_KEY=real\n"))
    assert os.environ["AGENTFW_TEST_KEY"] == "real"
    assert report.loaded == ["AGENTFW_TEST_KEY"]


# ---------------------------------------------------------------------------
# Fingerprints: enough to identify a key, useless for using one
# ---------------------------------------------------------------------------


def test_fingerprint_never_contains_the_secret():
    secret = "sk-proj-averyrealisticlookingsecretvalue-0123456789"
    fp = fingerprint(secret)
    assert secret not in fp
    assert not any(part in fp for part in (secret[:12], secret[-12:]))
    assert fp.startswith("sha8:")


def test_fingerprint_distinguishes_two_keys_of_the_same_length():
    """The whole point. The two keys in the incident were both 164 characters."""
    a, b = "k" * 164, "j" + "k" * 163
    assert fingerprint(a) != fingerprint(b)


def test_fingerprint_is_stable_and_names_the_absent_cases():
    assert fingerprint("x") == fingerprint("x")
    assert fingerprint(None) == "absent"
    assert fingerprint("") == "empty"


def test_credential_report_reports_fingerprints_not_presence(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "abc")
    out = credential_report()
    assert out["OPENAI_API_KEY"] == fingerprint("abc")
    assert "abc" not in str(out)
    assert out["ANTHROPIC_API_KEY"] in ("absent", "empty") or out[
        "ANTHROPIC_API_KEY"
    ].startswith("sha8:")


def test_a_missing_env_file_is_not_an_error(tmp_path):
    report = load_local_env(tmp_path / "nope.env")
    assert report == CredentialLoad()
    assert report.warnings() == []
