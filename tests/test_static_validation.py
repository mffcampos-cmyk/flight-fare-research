"""Static, fixture-based pytest tests for the skill's research rules.

These tests exercise ``tests.rules`` against synthetic fixtures only. They
perform no network access, no live-site automation, and no I/O beyond reading
the bundled ``observations.json`` fixture. Stdlib only plus pytest.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests import rules
from tests.rules import (
    blocked_source_once,
    classify_baggage,
    duration_to_seconds,
    enumerate_rolling_windows,
    passes_strict_duration_cap,
    sources_independent,
)

FIXTURES = Path(__file__).parent / "fixtures"
OBSERVATIONS = FIXTURES / "observations.json"


@pytest.fixture(scope="module")
def observations() -> list[dict]:
    """Load the synthetic observation rows once for the whole module."""
    with OBSERVATIONS.open(encoding="utf-8") as handle:
        return json.load(handle)["observations"]


# --------------------------------------------------------------------------- #
# 1. Strict duration filter: exactly 20:00:00 rejected; 19:59:59 passes.
# --------------------------------------------------------------------------- #


def test_strict_cap_rejects_exactly_20h():
    assert passes_strict_duration_cap("20:00:00") is False


def test_strict_cap_rejects_above_20h():
    assert passes_strict_duration_cap("20:00:01") is False
    assert passes_strict_duration_cap("21:03:00") is False


def test_strict_cap_passes_just_under_20h():
    assert passes_strict_duration_cap("19:59:59") is True


def test_strict_cap_passes_well_under_20h():
    assert passes_strict_duration_cap("07:15:00") is True


@pytest.mark.parametrize("duration", ["-1:00:00", "19:60:00", "19:00:60", "1:00:00", " 19:00:00", "19:00:-1", "aa:00:00"])
def test_duration_parser_rejects_malformed_values(duration):
    with pytest.raises(ValueError):
        duration_to_seconds(duration)


def test_duration_parsing():
    assert duration_to_seconds("20:00:00") == 72000
    assert duration_to_seconds("19:59:59") == 71999
    assert duration_to_seconds("00:00:01") == 1


# --------------------------------------------------------------------------- #
# 2. Matched rolling date windows preserved exactly, not collapsed.
# --------------------------------------------------------------------------- #


def test_rolling_windows_enumerated_exactly():
    windows = enumerate_rolling_windows(5, 10, 10)
    assert windows == [
        (5, 15),
        (6, 16),
        (7, 17),
        (8, 18),
        (9, 19),
        (10, 20),
    ]


def test_rolling_window_count_is_explicit():
    windows = enumerate_rolling_windows(5, 10, 10)
    assert len(windows) == 6  # six exact windows: 5->15 .. 10->20


def test_rolling_windows_not_collapsed():
    # Each paid window is preserved as its own pair (fixed length, distinct dates).
    windows = enumerate_rolling_windows(5, 10, 10)
    outbounds = {out for out, _ret in windows}
    assert outbounds == {5, 6, 7, 8, 9, 10}
    assert windows == sorted(windows)  # deterministic, ascending


def test_rolling_windows_single():
    assert enumerate_rolling_windows(7, 7, 3) == [(7, 10)]


# --------------------------------------------------------------------------- #
# 3. Baggage classification: exactly one of included | fee required | unverified.
# --------------------------------------------------------------------------- #


def test_baggage_classify_included():
    assert classify_baggage({"baggage": "included"}) == "included"


def test_baggage_classify_fee_required():
    assert classify_baggage({"baggage": "fee required"}) == "fee required"
    assert classify_baggage({"baggage": "first checked bag costs extra"}) == "fee required"


def test_baggage_classify_unverified():
    assert classify_baggage({"baggage": ""}) == "unverified"
    assert classify_baggage({}) == "unverified"
    assert classify_baggage({"baggage": "unverified"}) == "unverified"


def test_baggage_always_exactly_one_label():
    labels = {
        classify_baggage(row)
        for row in [
            {"baggage": "included"},
            {"baggage": "fee required"},
            {"baggage": ""},
        ]
    }
    assert labels <= {"included", "fee required", "unverified"}


# --------------------------------------------------------------------------- #
# 4. Source independence: shared inventory backend => NOT independent.
# --------------------------------------------------------------------------- #


def test_two_frontends_sharing_backend_not_independent():
    a = {"frontend": "frontend-A", "inventory_backend": "inventory-1"}
    b = {"frontend": "frontend-B", "inventory_backend": "inventory-1"}
    assert sources_independent(a, b) is False


def test_same_frontend_not_independent():
    a = {"frontend": "frontend-A", "inventory_backend": "inventory-1"}
    b = {"frontend": "frontend-A", "inventory_backend": "inventory-2"}
    assert sources_independent(a, b) is False


@pytest.mark.parametrize("field", ["frontend", "inventory_backend"])
@pytest.mark.parametrize("unknown", [None, "", "   "])
def test_unknown_source_identity_does_not_prove_independence(field, unknown):
    a = {"frontend": "frontend-A", "inventory_backend": "inventory-1"}
    b = {"frontend": "frontend-B", "inventory_backend": "inventory-2"}
    a[field] = unknown
    assert sources_independent(a, b) is False
    assert sources_independent(b, a) is False
    del a[field]
    assert sources_independent(a, b) is False


def test_distinct_frontend_and_backend_are_independent():
    a = {"frontend": "frontend-A", "inventory_backend": "inventory-1"}
    b = {"frontend": "frontend-B", "inventory_backend": "inventory-2"}
    assert sources_independent(a, b) is True


# --------------------------------------------------------------------------- #
# 5. Blocked-source one-attempt: recorded once, not retried.
# --------------------------------------------------------------------------- #


def test_blocked_source_recorded_once_not_retried():
    attempts = [
        {"source": "src-A", "blocked": True, "failure": "403"},
        {"source": "src-A", "blocked": True, "failure": "403 retry"},  # retry of src-A
        {"source": "src-B", "blocked": True, "failure": "CAPTCHA"},
    ]
    kept = blocked_source_once(attempts)
    assert [a["source"] for a in kept] == ["src-A", "src-B"]
    # src-A's retry (2nd blocked attempt) is dropped; only one record survives.
    assert sum(1 for a in kept if a["source"] == "src-A") == 1


def test_non_blocked_attempts_ignored_by_blocked_filter():
    attempts = [
        {"source": "src-A", "blocked": False, "price": "1"},
        {"source": "src-B", "blocked": True, "failure": "403"},
    ]
    assert blocked_source_once(attempts) == [
        {"source": "src-B", "blocked": True, "failure": "403"}
    ]


# --------------------------------------------------------------------------- #
# Fixture-driven tests over observations.json.
# --------------------------------------------------------------------------- #


def test_fixture_has_all_expected_states(observations):
    states = {row["state"] for row in observations}
    assert {"populated", "blocked", "empty", "stale"} <= states


def test_fixture_baggage_covers_all_labels(observations):
    populated = [r for r in observations if r.get("state") == "populated"]
    labels = {classify_baggage(r) for r in populated}
    assert labels == {"included", "fee required", "unverified"}


def test_fixture_contains_a_duration_cap_failure(observations):
    # obs-overcap-05 has duration 20:00:00 => must FAIL a strict under-20 cap.
    # Only retrieval rows carry a journey duration; blocked/empty/stale do not.
    timed = [r for r in observations if "duration" in r]
    failing = [r for r in timed if not passes_strict_duration_cap(r["duration"])]
    assert failing, "expected at least one observation failing the 20h cap"
    assert [r["id"] for r in failing] == ["obs-overcap-05"]


def test_fixture_just_under_cap_passes(observations):
    # obs-unverified-04 at 19:59:59 must PASS the strict under-20 cap.
    row = next(r for r in observations if r["id"] == "obs-unverified-04")
    assert passes_strict_duration_cap(row["duration"]) is True


def test_fixture_sources_are_synthetic(observations):
    # No real booking tokens / airport codes; all routes are fake three-letters.
    for row in observations:
        if "route" in row:
            assert len(row["route"]) == 7, row["route"]  # e.g. "AAA-ZZZ"


def test_baggage_fixture_rows_map_exactly(observations):
    expected = {
        "obs-included-01": "included",
        "obs-fee-02": "fee required",
        "obs-fee-03": "fee required",
        "obs-unverified-04": "unverified",
        "obs-overcap-05": "included",
        "obs-stale-09": "unverified",
        "obs-included-10": "included",
    }
    for row in observations:
        if row["id"] in expected:
            assert classify_baggage(row) == expected[row["id"]]


def test_imports_have_no_stdlib_network_side_effects():
    # Guard: rules must not import any network-capable stdlib module.
    import inspect

    source = inspect.getsource(rules)
    for banned in ("import socket", "import urllib", "import requests", "http.client"):
        assert banned not in source
