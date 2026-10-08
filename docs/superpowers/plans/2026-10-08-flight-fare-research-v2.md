# Flight Fare Research 2.0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restructure the flight-fare-research skill so every recommendation is evidence-qualified, coverage is checked by a shipped script, Cowork gets the same skill as a zip, and new sources are probed live.

**Architecture:** `skill/` stays the single canonical tree; a new stdlib script `skill/scripts/run_log.py` keeps one run's contract, rows, computed statuses, coverage and completeness check; `source_ledger.py` gains engine tracking and candidate sources; `SKILL.md` becomes a ≤2,000-word workflow pointing to focused references; `scripts/package.py` refreshes host copies and builds a deterministic Cowork zip.

**Tech Stack:** Python 3 standard library (scripts), pytest (tests only), Markdown (skill), Node Playwright 1.56.1 + `/opt/pw-browsers` Chromium (live probe only, never committed).

**Spec:** `docs/superpowers/specs/2026-10-08-flight-fare-research-v2-design.md`

## Global Constraints

- Edit skill content only under `skill/`; after any change there run `python3 scripts/package.py` and commit the regenerated `integrations/*/` copies in the same commit.
- Every commit passes `python3 scripts/validate.py --strict` and `python3 -m pytest tests/ -q`.
- Skill scripts: Python standard library only, no network access, `from __future__ import annotations`, runnable as `python3 <skill_dir>/scripts/<name>.py`.
- Tests never touch live sites or the network.
- `run_log.py` exit codes: `0` ok/complete, `2` usage or validation error, `4` incomplete. `source_ledger.py` keeps `0`, `2`, `3`.
- Runs root precedence: `$FFR_RUNS`, else `$XDG_STATE_HOME/flight-fare-research/runs`, else `~/.local/state/flight-fare-research/runs`.
- `SKILL.md` body ≤ 2,000 words; frontmatter `description` ≤ 1,024 characters.
- Release version `2.0.0` in `SKILL.md` frontmatter, `integrations/claude-code/.claude-plugin/plugin.json` and the top `CHANGELOG.md` heading.
- Never add instructions to enable CAPTCHA solving, proxy/TLS rotation, fingerprint changes, session import or private-API reverse engineering; never book or pay.
- Use synthetic airport codes (`AAA`, `ZZZ`, `BBB`, `CCC`, `YYY`) in test fixtures.
- Commit messages end with:
  ```
  Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_01W4jXHDFWuvK9xPsvNHwJuC
  ```

## Review Focus

1. Agents write `retrieved_at` without a timezone (`2026-10-08T14:03:00`) → `add` rejects it with a message naming "timezone" (Task 2).
2. Agents paste display prices (`"CHF 203.85"`, `"1'234.50"`) into `price` → `add` rejects with a message naming "price" (Task 2).
3. Rolling windows crossing a month or year end (`2026-12-28` + 7 days) → real date arithmetic gives `2027-01-04` (Task 1).
4. A session dies mid-append and leaves a truncated last line in `rows.jsonl` → loading ignores it and the next `add` trims it instead of corrupting the log (Task 4).
5. `check`/`coverage`/`add` run before any `init` → exit 2 with a hint to run `init`, no traceback (Task 4).

---

### Task 1: `run_log.py` contract, date expansion, cells and `init`

**Files:**
- Create: `skill/scripts/run_log.py`
- Create: `tests/run_log_helpers.py`
- Test: `tests/test_run_log_contract.py`

**Interfaces:**
- Produces (in `run_log.py`):
  - `HACKS = ("split", "open_jaw", "nearby_origin", "alt_destination", "stopover")`
  - `CABINS = ("economy", "premium", "business", "first")`
  - `EXIT_OK, EXIT_USAGE, EXIT_INCOMPLETE = 0, 2, 4`
  - `duration_to_seconds(hhmmss: str) -> int` — strict two-digit `HH:MM:SS`, raises `ValueError`
  - `validate_contract(contract: dict) -> list[str]` — `[]` when valid
  - `normalize_contract(contract: dict) -> dict` — returns a copy with defaults filled: `nearby_origins: []`, `alt_destinations: []`, `max_duration: None`, `positioning: {"allowed": False, "rail_ok": False, "overnight_ok": False}`, `self_transfer_ok: False`, `hacks` (full: the four non-stopover hacks; quick: `["nearby_origin"]`), `event: None`, `assumptions: []`, `travelers.children_ages: []`, `travelers.infants: 0`; `build_cells` and `init` use it
  - `expand_dates(dates: dict, trip_type: str) -> list[list]` — `[[out_iso, ret_iso_or_None], ...]`, sorted
  - `build_cells(contract: dict) -> list[dict]` — each `{"id": str, "kind": "baseline"|"hack"|"crosscheck"|"reprice", "cabin": str, "auto": None | {"as": "na", "reason": str}}`; baseline cells also carry `origin`, `destination`, `outbound_date`, `return_date`; hack cells carry `hack`
  - `runs_root() -> str`
  - `main(argv: list[str] | None = None) -> int` with subcommand `init --contract FILE [--runs-root DIR]`
- Produces (in `tests/run_log_helpers.py`): `run_log` (imported module), `contract(**over) -> dict`, `direction(dir="out", **over) -> dict`, `ticket(**over) -> dict`, `row(**over) -> dict`, `records(*rows) -> list[dict]`, `cli(*args, env=None, input=None) -> subprocess.CompletedProcess`, `write_json(path, obj) -> Path`

Decisions not in the spec: `run_id` is required (it names the run directory) and must match `^[a-z0-9][a-z0-9-]*$`. One-way contracts give dates as `{"outbound": ["YYYY-MM-DD", ...]}`. Cartesian expansion drops pairs whose return is before the outbound. Quick scope always has exactly one hack cell, `nearby_origin`; full scope uses `contract["hacks"]` or the default four (all of `HACKS` except `stopover`), in `HACKS` order. Cell id formats: `<cabin>/baseline/<O>-<D>/<out>_<ret>` (one-way: `<cabin>/baseline/<O>-<D>/<out>`), `<cabin>/hack/<hack>`, `<cabin>/crosscheck`, `<cabin>/reprice`; cabins in contract order, then baseline cells in origin, destination, date-pair order. Auto-`na` reasons, exactly: `"positioning not allowed"`, `"no nearby origins given"` (positioning allowed but list empty), `"one-way trip"` (split, open_jaw), `"no alternative destinations"`. `init` saves the contract with added keys `date_pairs` and `cells`, creates an empty `rows.jsonl`, and prints the run directory.

- [ ] **Step 1: Write `tests/run_log_helpers.py`**

```python
"""Shared builders for run_log tests (synthetic data, no network)."""
import json, os, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skill" / "scripts" / "run_log.py"
sys.dont_write_bytecode = True  # never leave __pycache__ inside skill/
sys.path.insert(0, str(SCRIPT.parent))
import run_log  # noqa: E402

def contract(**over):
    c = {"run_id": "t1", "scope": "quick", "trip_type": "return",
         "travelers": {"adults": 1, "children_ages": [], "infants": 0},
         "currency": "CHF", "origins": ["AAA"], "nearby_origins": [],
         "destinations": ["ZZZ"], "alt_destinations": [],
         "dates": {"pairs": [["2026-11-05", "2026-11-12"]]},
         "cabins": ["economy"], "bags": {"checked_per_person": 1},
         "max_duration": {"value": "20:00:00", "strict": True},
         "positioning": {"allowed": False, "rail_ok": False, "overnight_ok": False},
         "self_transfer_ok": False, "event": None, "assumptions": []}
    c.update(over)
    return c

def direction(dir="out", **over):
    base = {"out": {"from": "AAA", "to": "ZZZ", "dep": "2026-11-05T07:10:00",
                    "arr": "2026-11-05T09:05:00", "duration": "02:55:00"},
            "ret": {"from": "ZZZ", "to": "AAA", "dep": "2026-11-12T18:00:00",
                    "arr": "2026-11-12T22:00:00", "duration": "03:00:00"}}[dir]
    d = dict(base, dir=dir, stops=0, airlines=["XX"], airport_change=False, self_transfer=False)
    d.update(over)
    return d

def ticket(**over):
    t = {"price": 400.0, "quote_state": "completed", "provider": "XX",
         "baggage": "included", "bag_fee": None, "booking_url": "https://example.test/book"}
    t.update(over)
    return t

def row(**over):
    r = {"source": "google-flights", "family": "google", "engine": "test", "outcome": "populated",
         "url": "https://example.test/search", "retrieved_at": "2026-10-08T14:03:00+02:00",
         "cabin": "economy", "cabin_label": "Economy", "hack": None,
         "origin": "AAA", "destination": "ZZZ",
         "outbound_date": "2026-11-05", "return_date": "2026-11-12",
         "currency": "CHF", "fx": None, "price_basis": "total",
         "tickets": [ticket()], "directions": [direction("out"), direction("ret")],
         "components": {}, "positioning_overnight": False, "supersedes": None, "notes": ""}
    r.update(over)
    return r

def records(*rows):
    return [dict(r, type="row", id=f"r{i}") for i, r in enumerate(rows, 1)]

def write_json(path, obj):
    path = Path(path); path.write_text(json.dumps(obj)); return path

def cli(*args, env=None, input=None):
    e = {k: v for k, v in os.environ.items() if k not in ("FFR_RUNS", "XDG_STATE_HOME")}
    e.update(env or {})
    return subprocess.run([sys.executable, str(SCRIPT), *map(str, args)],
                          capture_output=True, text=True, env=e, input=input)
```

- [ ] **Step 2: Write the failing tests in `tests/test_run_log_contract.py`**

```python
import json
import pytest
from tests.run_log_helpers import run_log, contract, cli, write_json

POS = {"allowed": True, "rail_ok": True, "overnight_ok": False}

def test_valid_contract_has_no_errors():
    assert run_log.validate_contract(contract()) == []

@pytest.mark.parametrize("field", ["run_id", "scope", "trip_type", "currency", "origins",
                                   "destinations", "dates", "cabins", "bags", "travelers"])
def test_missing_required_field_is_reported(field):
    c = contract(); del c[field]
    assert any(field in e for e in run_log.validate_contract(c))

def test_adults_must_be_at_least_one():
    assert any("adults" in e for e in run_log.validate_contract(
        contract(travelers={"adults": 0, "children_ages": [], "infants": 0})))

def test_checked_bags_required():
    assert any("checked_per_person" in e for e in run_log.validate_contract(contract(bags={})))

@pytest.mark.parametrize("over", [{"scope": "medium"}, {"trip_type": "multi"},
                                  {"cabins": ["coach"]}, {"hacks": ["hidden_city"]},
                                  {"max_duration": {"value": "20h", "strict": True}},
                                  {"run_id": "Bad Id"}])
def test_invalid_values_are_reported(over):
    assert run_log.validate_contract(contract(**over)) != []

def test_rolling_dates_expand_to_matched_pairs():
    pairs = run_log.expand_dates({"rolling": {"first_outbound": "2026-03-05",
                                              "last_outbound": "2026-03-10", "trip_days": 10}}, "return")
    assert pairs == [["2026-03-05", "2026-03-15"], ["2026-03-06", "2026-03-16"],
                     ["2026-03-07", "2026-03-17"], ["2026-03-08", "2026-03-18"],
                     ["2026-03-09", "2026-03-19"], ["2026-03-10", "2026-03-20"]]

def test_rolling_dates_cross_year_boundary():
    assert run_log.expand_dates({"rolling": {"first_outbound": "2026-12-28",
                                             "last_outbound": "2026-12-29", "trip_days": 7}}, "return") == \
        [["2026-12-28", "2027-01-04"], ["2026-12-29", "2027-01-05"]]

def test_cartesian_requires_confirmation():
    c = contract(dates={"cartesian": {"outbound_from": "2026-11-05", "outbound_to": "2026-11-06",
                                      "return_from": "2026-11-12", "return_to": "2026-11-13"}})
    assert any("confirmed" in e for e in run_log.validate_contract(c))

def test_cartesian_expands_every_pair_when_confirmed():
    assert run_log.expand_dates({"cartesian": {"outbound_from": "2026-11-05", "outbound_to": "2026-11-06",
                                               "return_from": "2026-11-12", "return_to": "2026-11-13",
                                               "confirmed": True}}, "return") == \
        [["2026-11-05", "2026-11-12"], ["2026-11-05", "2026-11-13"],
         ["2026-11-06", "2026-11-12"], ["2026-11-06", "2026-11-13"]]

def test_cartesian_drops_returns_before_outbound():
    assert run_log.expand_dates({"cartesian": {"outbound_from": "2026-11-10", "outbound_to": "2026-11-12",
                                               "return_from": "2026-11-11", "return_to": "2026-11-11",
                                               "confirmed": True}}, "return") == \
        [["2026-11-10", "2026-11-11"], ["2026-11-11", "2026-11-11"]]

def test_one_way_dates_have_no_return():
    assert run_log.expand_dates({"outbound": ["2026-11-05"]}, "one_way") == [["2026-11-05", None]]

def test_quick_cells():
    cells = run_log.build_cells(contract())
    assert [c["id"] for c in cells] == ["economy/baseline/AAA-ZZZ/2026-11-05_2026-11-12",
                                        "economy/hack/nearby_origin", "economy/crosscheck", "economy/reprice"]
    assert cells[1]["auto"] == {"as": "na", "reason": "positioning not allowed"}

def test_quick_nearby_origin_needs_airports():
    cells = run_log.build_cells(contract(positioning=POS))
    assert cells[1]["auto"] == {"as": "na", "reason": "no nearby origins given"}
    cells = run_log.build_cells(contract(positioning=POS, nearby_origins=["BBB"]))
    assert cells[1]["auto"] is None

def test_full_cells_cover_pairs_origins_cabins_and_default_hacks():
    c = contract(scope="full", origins=["AAA", "CCC"], cabins=["economy", "business"],
                 dates={"rolling": {"first_outbound": "2026-11-05", "last_outbound": "2026-11-07", "trip_days": 7}},
                 alt_destinations=["YYY"], nearby_origins=["BBB"], positioning=POS)
    ids = [x["id"] for x in run_log.build_cells(c)]
    assert sum("/baseline/" in i for i in ids) == 3 * 2 * 2
    assert [i for i in ids if i.startswith("economy/hack/")] == [
        "economy/hack/split", "economy/hack/open_jaw", "economy/hack/nearby_origin", "economy/hack/alt_destination"]

def test_stopover_cell_only_when_requested():
    ids = [x["id"] for x in run_log.build_cells(contract(scope="full", hacks=["split", "stopover"]))]
    assert "economy/hack/stopover" in ids and "economy/hack/open_jaw" not in ids

def test_forbidden_hacks_auto_resolved_na():
    c = contract(scope="full", trip_type="one_way", dates={"outbound": ["2026-11-05"]})
    auto = {x["id"]: x["auto"] for x in run_log.build_cells(c)}
    assert auto["economy/baseline/AAA-ZZZ/2026-11-05"] is None
    assert auto["economy/hack/split"] == {"as": "na", "reason": "one-way trip"}
    assert auto["economy/hack/open_jaw"] == {"as": "na", "reason": "one-way trip"}
    assert auto["economy/hack/alt_destination"] == {"as": "na", "reason": "no alternative destinations"}

def test_init_writes_contract_and_empty_log(tmp_path):
    r = cli("init", "--contract", write_json(tmp_path / "c.json", contract()), "--runs-root", tmp_path / "runs")
    assert r.returncode == 0, r.stderr
    d = tmp_path / "runs" / "t1"
    saved = json.loads((d / "contract.json").read_text())
    assert saved["date_pairs"] == [["2026-11-05", "2026-11-12"]] and len(saved["cells"]) == 4
    assert (d / "rows.jsonl").read_text() == ""

def test_init_fills_defaults(tmp_path):
    c = {k: v for k, v in contract(scope="full").items()
         if k not in ("nearby_origins", "alt_destinations", "max_duration", "positioning",
                      "self_transfer_ok", "event", "assumptions")}
    assert cli("init", "--contract", write_json(tmp_path / "c.json", c), "--runs-root", tmp_path / "runs").returncode == 0
    saved = json.loads((tmp_path / "runs" / "t1" / "contract.json").read_text())
    assert saved["max_duration"] is None and saved["positioning"]["allowed"] is False
    assert saved["self_transfer_ok"] is False
    assert saved["hacks"] == ["split", "open_jaw", "nearby_origin", "alt_destination"]

def test_init_rejects_invalid_contract(tmp_path):
    c = contract(); del c["cabins"]
    r = cli("init", "--contract", write_json(tmp_path / "c.json", c), "--runs-root", tmp_path / "runs")
    assert r.returncode == 2 and "cabins" in r.stderr
    assert not (tmp_path / "runs" / "t1").exists()

def test_init_refuses_existing_run(tmp_path):
    args = ("init", "--contract", write_json(tmp_path / "c.json", contract()), "--runs-root", tmp_path / "runs")
    assert cli(*args).returncode == 0
    r = cli(*args)
    assert r.returncode == 2 and "exists" in r.stderr

def test_runs_root_precedence(tmp_path, monkeypatch):
    monkeypatch.setenv("FFR_RUNS", str(tmp_path / "a"))
    assert run_log.runs_root() == str(tmp_path / "a")
    monkeypatch.delenv("FFR_RUNS")
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "x"))
    assert run_log.runs_root() == str(tmp_path / "x" / "flight-fare-research" / "runs")
    monkeypatch.delenv("XDG_STATE_HOME")
    monkeypatch.setenv("HOME", str(tmp_path / "h"))
    assert run_log.runs_root() == str(tmp_path / "h" / ".local" / "state" / "flight-fare-research" / "runs")
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `python3 -m pytest tests/test_run_log_contract.py -q`
Expected: collection error `ModuleNotFoundError: No module named 'run_log'`.

- [ ] **Step 4: Implement the Task 1 interfaces in `skill/scripts/run_log.py`**

Module docstring lists every subcommand (later tasks extend it). Use `datetime.date.fromisoformat` and `timedelta` for date arithmetic; argparse subparsers; write `contract.json` with `json.dump(indent=2)`; refuse an existing run directory with exit 2 and a message containing `exists`; validation errors print one line each to stderr and exit 2.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python3 -m pytest tests/test_run_log_contract.py -q`
Expected: all pass.

- [ ] **Step 6: Package, validate, commit**

```bash
python3 scripts/package.py && python3 scripts/validate.py --strict && python3 -m pytest tests/ -q
git add skill/scripts/run_log.py integrations tests/run_log_helpers.py tests/test_run_log_contract.py
git commit -m "feat(run_log): contract validation, date expansion, comparison cells and init"
```

---

### Task 2: `run_log.py` rows, computed statuses and `add`

**Files:**
- Modify: `skill/scripts/run_log.py`
- Test: `tests/test_run_log_rows.py`

**Interfaces:**
- Consumes: Task 1 (`validate_contract`, `expand_dates`, `duration_to_seconds`, helpers).
- Produces:
  - `validate_row(row: dict, contract: dict) -> list[str]`
  - `row_status(row: dict, contract: dict, superseded: set[str]) -> tuple[str, list[str]]` — status in `("superseded", "attempt", "rejected", "lead", "qualified")`
  - `all_in(row: dict, contract: dict) -> float` — rounded to 2 decimals; only meaningful for qualified rows
  - `lower_bound(row: dict, contract: dict) -> float` — same sum with unknown parts as 0
  - `row_cell_id(row: dict) -> str` — the baseline or hack cell id the row belongs to
  - `load_run(run_dir: str) -> tuple[dict, list[dict]]` and `append_record(run_dir: str, record: dict) -> None` (Task 4 hardens both)
  - `resolve_run_dir(arg: str | None) -> str` — `--run` value, else the most recently modified directory under `runs_root()`; raises `SystemExit(2)` with a message containing `init` when none exists
  - subcommand `add --row FILE|- [--run DIR]` printing `"<id> <status>"` plus `": " + "; ".join(reasons)` when reasons exist

Exact reason strings. Rejected: `f"{dir} duration {dur} breaks strict cap {cap}"` (or `inclusive`), `"self-transfer not allowed"`, `"cabin not requested"`, `"dates not in contract"`, `"origin not in contract"`, `"destination not in contract"`, `"positioning not allowed"`, `"overnight positioning not allowed"`. Lead: `"outbound not selected"`, `"return not selected"` (return trips only), `f"duration unknown ({dir})"`, `"list fare not repriced"`, `"baggage unverified"`, `"bag fee unknown"`, `f"{name} unpriced"`, `"currency differs; no fx recorded"`, `"per-person price with infants; record the total"`. Bag reasons apply only when `checked_per_person > 0`. Allowed origins: baseline and non-positioning hacks use `origins`; `nearby_origin` rows use `nearby_origins`. Allowed destinations: baseline uses `destinations`; `alt_destination` uses `alt_destinations`; `open_jaw` accepts either. A `nearby_origin` row or any row whose `components` has a `positioning` key is rejected `"positioning not allowed"` when `positioning.allowed` is false. All-in: `sum(ticket prices) × (adults + len(children_ages) if price_basis == "per_person" else 1) + sum(bag_fee for fee_required tickets when bags requested) + sum(non-null components)`, then `× fx["rate"]` when `fx` is set. Row validation: required for every row `source, family, engine, outcome, url, retrieved_at, cabin`; populated rows also need `currency, origin, destination, outbound_date, tickets` (non-empty) and `directions` (a list); `retrieved_at` must parse with `datetime.fromisoformat` and carry `tzinfo`; ticket `price` must be an `int`/`float` (not `bool`) ≥ 0; enums `outcome ∈ {populated, blocked, empty, error}`, `quote_state ∈ {list, completed, repriced}`, `baggage ∈ {included, fee_required, unverified}`, `price_basis ∈ {total, per_person}`, `hack ∈ HACKS ∪ {None}`. `add` also rejects a `supersedes` id that is not already in the log. Ids are `r1, r2, …` by count of row records.

- [ ] **Step 1: Write the failing tests in `tests/test_run_log_rows.py`**

```python
import json
import pytest
from tests.run_log_helpers import run_log, contract, row, ticket, direction, cli, write_json

POS = {"allowed": True, "rail_ok": True, "overnight_ok": False}

def status(r, c=None, superseded=()):
    return run_log.row_status(dict(r, id="r1"), c or contract(), set(superseded))

def test_complete_row_is_qualified():
    assert status(row()) == ("qualified", [])

def test_strict_cap_rejects_exactly_20h():
    r = row(directions=[direction("out", duration="20:00:00"), direction("ret")])
    assert status(r) == ("rejected", ["out duration 20:00:00 breaks strict cap 20:00:00"])

def test_strict_cap_passes_one_second_under():
    assert status(row(directions=[direction("out", duration="19:59:59"), direction("ret")]))[0] == "qualified"

def test_inclusive_cap_accepts_exactly_20h():
    c = contract(max_duration={"value": "20:00:00", "strict": False})
    assert status(row(directions=[direction("out", duration="20:00:00"), direction("ret")]), c)[0] == "qualified"

def test_no_cap_when_max_duration_null():
    c = contract(max_duration=None)
    assert status(row(directions=[direction("out", duration="30:00:00"), direction("ret")]), c)[0] == "qualified"

@pytest.mark.parametrize("over,reason", [
    ({"directions": [direction("out")]}, "return not selected"),
    ({"directions": [direction("ret")]}, "outbound not selected"),
    ({"tickets": [ticket(quote_state="list")]}, "list fare not repriced"),
    ({"tickets": [ticket(baggage="unverified")]}, "baggage unverified"),
    ({"tickets": [ticket(baggage="fee_required", bag_fee=None)]}, "bag fee unknown"),
    ({"components": {"hotel": None}}, "hotel unpriced"),
    ({"currency": "EUR"}, "currency differs; no fx recorded"),
    ({"directions": [direction("out", duration=None), direction("ret")]}, "duration unknown (out)"),
])
def test_lead_reasons(over, reason):
    s, reasons = status(row(**over))
    assert s == "lead" and reason in reasons

def test_infants_with_per_person_price_is_lead():
    c = contract(travelers={"adults": 1, "children_ages": [], "infants": 1})
    assert "per-person price with infants; record the total" in status(row(price_basis="per_person"), c)[1]

def test_unverified_bag_qualifies_when_no_checked_bags_requested():
    c = contract(bags={"checked_per_person": 0})
    assert status(row(tickets=[ticket(baggage="unverified")]), c)[0] == "qualified"

def test_fee_required_with_known_fee_qualifies():
    r = row(tickets=[ticket(baggage="fee_required", bag_fee=60.0)])
    assert status(r)[0] == "qualified"
    assert run_log.all_in(r, contract()) == 460.0

@pytest.mark.parametrize("over,cover,reason", [
    ({"directions": [direction("out", self_transfer=True), direction("ret")]}, {}, "self-transfer not allowed"),
    ({"cabin": "business"}, {}, "cabin not requested"),
    ({"outbound_date": "2026-11-06"}, {}, "dates not in contract"),
    ({"origin": "CCC"}, {}, "origin not in contract"),
    ({"destination": "YYY"}, {}, "destination not in contract"),
    ({"hack": "nearby_origin", "origin": "BBB"}, {"nearby_origins": ["BBB"]}, "positioning not allowed"),
    ({"components": {"positioning": 45.0}}, {}, "positioning not allowed"),
    ({"positioning_overnight": True}, {"positioning": POS}, "overnight positioning not allowed"),
])
def test_rejections(over, cover, reason):
    s, reasons = status(row(**over), contract(**cover))
    assert s == "rejected" and reason in reasons

def test_rejection_beats_lead():
    r = row(tickets=[ticket(quote_state="list")],
            directions=[direction("out", duration="21:00:00"), direction("ret")])
    assert status(r) == ("rejected", ["out duration 21:00:00 breaks strict cap 20:00:00"])

def test_superseded_and_attempt_statuses():
    assert status(row(), superseded={"r1"}) == ("superseded", [])
    assert status({"source": "x", "family": "x", "engine": "t", "outcome": "blocked",
                   "url": "https://e.test", "retrieved_at": "2026-10-08T10:00:00+00:00",
                   "cabin": "economy"}) == ("attempt", [])

def test_multi_ticket_rows_need_every_ticket_qualified():
    assert "list fare not repriced" in status(row(tickets=[ticket(), ticket(quote_state="list")]))[1]
    assert "baggage unverified" in status(row(tickets=[ticket(), ticket(baggage="unverified")]))[1]

def test_all_in_sums_parts():
    c = contract(travelers={"adults": 2, "children_ages": [], "infants": 0}, positioning=POS)
    r = row(price_basis="per_person", tickets=[ticket(price=200.0, baggage="fee_required", bag_fee=60.0)],
            components={"positioning": 45.0, "hotel": 90.0})
    assert run_log.all_in(r, c) == 595.0

def test_all_in_applies_fx():
    r = row(currency="EUR", fx={"rate": 0.95, "date": "2026-10-08", "source": "ECB"})
    assert status(r)[0] == "qualified" and run_log.all_in(r, contract()) == 380.0

def test_lower_bound_counts_unknowns_as_zero():
    c = contract(positioning=POS)
    r = row(tickets=[ticket(price=300.0, quote_state="list", baggage="unverified")], components={"positioning": None})
    assert run_log.lower_bound(r, c) == 300.0
    assert run_log.lower_bound(dict(r, components={"positioning": 45.0}), c) == 345.0

def test_row_cell_id():
    assert run_log.row_cell_id(row()) == "economy/baseline/AAA-ZZZ/2026-11-05_2026-11-12"
    assert run_log.row_cell_id(row(hack="split")) == "economy/hack/split"

def test_validate_row_accepts_complete_row():
    assert run_log.validate_row(row(), contract()) == []

@pytest.mark.parametrize("field", ["source", "family", "engine", "url", "retrieved_at", "cabin", "tickets"])
def test_validate_row_requires_fields(field):
    r = row(); del r[field]
    assert any(field in e for e in run_log.validate_row(r, contract()))

def test_retrieved_at_needs_timezone():
    assert any("timezone" in e for e in run_log.validate_row(row(retrieved_at="2026-10-08T14:03:00"), contract()))

@pytest.mark.parametrize("price", ["CHF 203.85", "1'234.50", True, -1])
def test_price_must_be_non_negative_number(price):
    assert any("price" in e for e in run_log.validate_row(row(tickets=[ticket(price=price)]), contract()))

@pytest.mark.parametrize("over", [{"tickets": [ticket(baggage="maybe")]}, {"tickets": [ticket(quote_state="final")]},
                                  {"hack": "hidden_city"}, {"outcome": "teaser"}, {"price_basis": "each"}])
def test_unknown_enum_values_rejected(over):
    assert run_log.validate_row(row(**over), contract()) != []

def test_attempt_row_needs_no_tickets():
    attempt = {"source": "x", "family": "x", "engine": "t", "outcome": "blocked", "url": "https://e.test",
               "retrieved_at": "2026-10-08T10:00:00+00:00", "cabin": "economy"}
    assert run_log.validate_row(attempt, contract()) == []

@pytest.fixture
def run_dir(tmp_path):
    assert cli("init", "--contract", write_json(tmp_path / "c.json", contract()),
               "--runs-root", tmp_path / "runs").returncode == 0
    return tmp_path / "runs" / "t1"

def test_add_appends_and_reports_status(run_dir, tmp_path):
    f = write_json(tmp_path / "r.json", row())
    first, second = cli("add", "--run", run_dir, "--row", f), cli("add", "--run", run_dir, "--row", f)
    assert first.returncode == 0 and first.stdout.startswith("r1 qualified")
    assert second.stdout.startswith("r2 qualified")
    assert len((run_dir / "rows.jsonl").read_text().splitlines()) == 2

def test_add_reads_stdin_and_reports_reasons(run_dir):
    r = cli("add", "--run", run_dir, "--row", "-", input=json.dumps(row(tickets=[ticket(quote_state="list")])))
    assert r.returncode == 0 and r.stdout.startswith("r1 lead: list fare not repriced")

def test_add_invalid_row_appends_nothing(run_dir, tmp_path):
    r = cli("add", "--run", run_dir, "--row", write_json(tmp_path / "r.json", row(retrieved_at="2026-10-08T14:03:00")))
    assert r.returncode == 2 and (run_dir / "rows.jsonl").read_text() == ""

def test_add_supersedes_must_reference_existing_row(run_dir, tmp_path):
    r = cli("add", "--run", run_dir, "--row", write_json(tmp_path / "r.json", row(supersedes="r9")))
    assert r.returncode == 2 and "r9" in r.stderr
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m pytest tests/test_run_log_rows.py -q`
Expected: FAIL with `AttributeError: module 'run_log' has no attribute 'row_status'`.

- [ ] **Step 3: Implement the Task 2 interfaces in `skill/scripts/run_log.py`**

`row_status` order: superseded, attempt, rejected (collect every hard-gate reason), lead (collect every reason), qualified. Records in `rows.jsonl` are the row dict plus `"type": "row"`, `"id"`, `"added_at"` (UTC ISO). `append_record` writes one JSON line and flushes.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m pytest tests/test_run_log_rows.py tests/test_run_log_contract.py -q`
Expected: all pass.

- [ ] **Step 5: Package, validate, commit**

```bash
python3 scripts/package.py && python3 scripts/validate.py --strict && python3 -m pytest tests/ -q
git add skill/scripts/run_log.py integrations tests/test_run_log_rows.py
git commit -m "feat(run_log): row validation, computed lead/qualified statuses and add"
```

---

### Task 3: `run_log.py` ranking, pruning and risk flags

**Files:**
- Modify: `skill/scripts/run_log.py`
- Test: `tests/test_run_log_rank.py`

**Interfaces:**
- Consumes: Task 2 (`row_status`, `all_in`, `lower_bound`, `load_run`, `resolve_run_dir`).
- Produces:
  - `risk_flags(row: dict, contract: dict) -> list[str]`
  - `evaluate(contract: dict, records: list[dict]) -> list[dict]` — one entry per row record: `{"id", "cabin", "cell", "status", "reasons", "all_in" (float|None), "lower_bound" (float|None), "flags", "row"}`; `superseded` set comes from every record's `supersedes`
  - `rank(contract: dict, records: list[dict], cabin: str | None = None) -> dict` — `{cabin: {"best": float|None, "qualified": [eval...], "leads": [eval + {"pruned": bool}]}}`
  - subcommand `rank [--run DIR] [--cabin C] [--json]`

Flags, exactly: `f"mixed cabin: {cabin_label}"` when `"+"` is in `cabin_label`; `"airport change"`; `"next-day arrival"` when any direction's `arr` date is after its `dep` date (compare the date parts); `"separate tickets"` when more than one ticket; `"2+ stops"` when any direction has `stops >= 2`; `"self-transfer"`; `"positioning"` / `"hotel"` when those components are present. Qualified sort key: `(all_in, max direction seconds, total stops, id)`. Leads sort by `lower_bound`. `best` = lowest qualified `all_in` in the cabin; a lead is `pruned` when `best is not None and lower_bound >= best`. Text output per lead line includes `f"pruned: LB {lb:.2f} >= best {best:.2f}"` when pruned. Rejected, superseded and attempt rows appear in neither list.

- [ ] **Step 1: Write the failing tests in `tests/test_run_log_rank.py`**

```python
import json
from tests.run_log_helpers import run_log, contract, row, ticket, direction, records, cli, write_json

def test_qualified_ranked_by_all_in_then_duration():
    a = row(tickets=[ticket(price=500.0)])
    b = row(directions=[direction("out", duration="10:00:00"), direction("ret")])
    c = row()
    out = run_log.rank(contract(), records(a, b, c))["economy"]
    assert [q["id"] for q in out["qualified"]] == ["r3", "r2", "r1"] and out["best"] == 400.0

def test_leads_listed_with_reasons_and_bound():
    lead = run_log.rank(contract(), records(row(tickets=[ticket(price=300.0, quote_state="list")])))["economy"]["leads"][0]
    assert (lead["id"], lead["lower_bound"], lead["reasons"], lead["pruned"]) == \
        ("r1", 300.0, ["list fare not repriced"], False)

def test_lead_pruned_when_bound_reaches_best():
    recs = records(row(), row(hack="open_jaw", tickets=[ticket(price=420.0, quote_state="list")]),
                   row(hack="split", tickets=[ticket(price=400.0, quote_state="list")]))
    leads = {l["id"]: l["pruned"] for l in run_log.rank(contract(), recs)["economy"]["leads"]}
    assert leads == {"r2": True, "r3": True}

def test_pruned_lead_readmitted_when_best_superseded():
    lead = row(tickets=[ticket(price=450.0, quote_state="list")])
    assert run_log.rank(contract(), records(row(), lead))["economy"]["leads"][0]["pruned"] is True
    recs = records(row(), lead, row(supersedes="r1", tickets=[ticket(price=500.0)]))
    out = run_log.rank(contract(), recs)["economy"]
    assert out["best"] == 500.0 and out["leads"][0]["pruned"] is False

def test_rejected_rows_are_excluded():
    out = run_log.rank(contract(), records(row(directions=[direction("out", duration="22:00:00"), direction("ret")])))
    assert out["economy"]["qualified"] == [] and out["economy"]["leads"] == []

def test_rank_filters_by_cabin():
    c = contract(cabins=["economy", "business"])
    assert list(run_log.rank(c, records(row(), row(cabin="business")), cabin="business")) == ["business"]

def test_risk_flags():
    c = contract(positioning={"allowed": True, "rail_ok": True, "overnight_ok": True})
    r = row(cabin_label="Economy + Premium Economy", tickets=[ticket(), ticket()],
            directions=[direction("out", airport_change=True, stops=2), direction("ret")],
            components={"positioning": 45.0, "hotel": 90.0})
    assert run_log.risk_flags(r, c) == ["mixed cabin: Economy + Premium Economy", "airport change",
                                        "separate tickets", "2+ stops", "positioning", "hotel"]

def test_next_day_flag_uses_dates_not_clock_times():
    late = direction("out", dep="2026-11-05T23:30:00", arr="2026-11-06T01:10:00", duration="02:40:00")
    assert "next-day arrival" in run_log.risk_flags(row(directions=[late, direction("ret")]), contract())
    assert "next-day arrival" not in run_log.risk_flags(row(), contract())

def test_rank_cli_text_and_json(tmp_path):
    cli("init", "--contract", write_json(tmp_path / "c.json", contract()), "--runs-root", tmp_path / "runs")
    run = tmp_path / "runs" / "t1"
    cli("add", "--run", run, "--row", write_json(tmp_path / "a.json", row()))
    cli("add", "--run", run, "--row", write_json(tmp_path / "b.json",
        row(hack="open_jaw", tickets=[ticket(price=420.0, quote_state="list")])))
    text = cli("rank", "--run", run)
    assert text.returncode == 0 and "pruned: LB 420.00 >= best 400.00" in text.stdout
    assert json.loads(cli("rank", "--run", run, "--json").stdout)["economy"]["best"] == 400.0
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m pytest tests/test_run_log_rank.py -q`
Expected: FAIL with `AttributeError: module 'run_log' has no attribute 'rank'`.

- [ ] **Step 3: Implement the Task 3 interfaces in `skill/scripts/run_log.py`**

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m pytest tests/test_run_log_rank.py -q`
Expected: all pass.

- [ ] **Step 5: Package, validate, commit**

```bash
python3 scripts/package.py && python3 scripts/validate.py --strict && python3 -m pytest tests/ -q
git add skill/scripts/run_log.py integrations tests/test_run_log_rank.py
git commit -m "feat(run_log): ranking by qualified all-in with lower-bound pruning and risk flags"
```

---

### Task 4: `run_log.py` coverage, resolve and check; retire `tests/rules.py`

**Files:**
- Modify: `skill/scripts/run_log.py`
- Test: `tests/test_run_log_check.py`
- Delete: `tests/rules.py`, `tests/test_static_validation.py`, `tests/test_pruning.py`, `tests/fixtures/observations.json`

**Interfaces:**
- Consumes: Tasks 1–3 (`build_cells` output stored in `contract["cells"]`, `evaluate`, `rank`).
- Produces:
  - `cell_states(contract: dict, records: list[dict]) -> list[dict]` — `{"id", "kind", "cabin", "state": "open"|"done"|"resolved", "why": str, "rows": int}` (auto-`na` cells and `resolve` records give `resolved` with `why = f"{as}: {reason}"`; the latest `resolve` record for a cell wins)
  - `check(contract: dict, records: list[dict]) -> dict` — `{"complete": bool, "open": [{"cell", "why"}], "resolved": [{"cell", "why"}], "warn": [str]}`
  - subcommands `resolve CELL --as na|no_fare|none_qualify --reason TEXT [--run DIR]`, `coverage [--run DIR] [--json]`, `check [--run DIR] [--json]`

Done rules per spec §4. Open `why` strings, exactly: `"not attempted"`, `"only blocked/empty/error attempts"`, `f"{n} source family attempted"` / `f"{n} source families attempted"` (crosscheck, `n < 2`, counting distinct `family` over all non-superseded row records in the cabin), `"no qualified option"` (reprice), `f"unresolved lead(s): {', '.join(ids)}"` (hack cell whose populated rows include unpruned leads and no qualified row). Warn strings: `f"{cabin}: lead {id} may beat best qualified (LB {lb:.2f} < {best:.2f})"` for each unpruned lead when `best` exists; `f"{cabin}: only one source family returned results ({family})"` when exactly one family has populated rows. Text output of `check`: first line `COMPLETE` or `f"INCOMPLETE: {n} open item(s)"`, then `OPEN      <cell>  <why>`, `RESOLVED  <cell>  <why>`, `WARN      <msg>` lines; exit 0 or 4. `coverage` prints one line per cell `f"{state:<9}{id}  rows={n}  {why}"` and ends with `f"{closed}/{total} cells closed"`. `load_run` ignores an unparsable *last* line (stderr warning) and raises `ValueError` (exit 2) for an unparsable earlier line; `append_record` first truncates an unterminated trailing partial line.

- [ ] **Step 1: Write the failing tests in `tests/test_run_log_check.py`**

```python
import pytest
from tests.run_log_helpers import run_log, contract, row, ticket, direction, records, cli, write_json

BASE = "economy/baseline/AAA-ZZZ/2026-11-05_2026-11-12"

def full(**over):
    c = contract(scope="full", hacks=["split"], **over)
    c["date_pairs"] = run_log.expand_dates(c["dates"], c["trip_type"]); c["cells"] = run_log.build_cells(c)
    return c

def quick():
    c = contract()
    c["date_pairs"] = run_log.expand_dates(c["dates"], c["trip_type"]); c["cells"] = run_log.build_cells(c)
    return c

def blocked(family="edreams"):
    return {"source": family, "family": family, "engine": "t", "outcome": "blocked", "url": "https://e.test",
            "retrieved_at": "2026-10-08T10:00:00+00:00", "cabin": "economy", "hack": None, "origin": "AAA",
            "destination": "ZZZ", "outbound_date": "2026-11-05", "return_date": "2026-11-12"}

def open_items(c, recs):
    return {o["cell"]: o["why"] for o in run_log.check(c, recs)["open"]}

def test_nothing_attempted():
    assert open_items(quick(), []) == {BASE: "not attempted", "economy/crosscheck": "0 source families attempted",
                                       "economy/reprice": "no qualified option"}

def test_blocked_only_cell_stays_open():
    assert open_items(quick(), records(blocked()))[BASE] == "only blocked/empty/error attempts"

def test_complete_quick_run_with_single_family_warning():
    result = run_log.check(quick(), records(row(), blocked()))
    assert result["complete"] is True and result["open"] == []
    assert result["warn"] == ["economy: only one source family returned results (google)"]
    assert {"cell": "economy/hack/nearby_origin", "why": "na: positioning not allowed"} in result["resolved"]

def test_warns_about_cheaper_unqualified_leads():
    recs = records(row(), row(family="edreams", source="edreams", tickets=[ticket(price=250.0, quote_state="list")]))
    result = run_log.check(quick(), recs)
    assert result["complete"] is True
    assert result["warn"] == ["economy: lead r2 may beat best qualified (LB 250.00 < 400.00)"]

def test_hack_cell_open_while_lead_could_win():
    recs = records(row(), row(hack="split", tickets=[ticket(price=300.0, quote_state="list")]), blocked())
    assert open_items(full(), recs) == {"economy/hack/split": "unresolved lead(s): r2"}

@pytest.mark.parametrize("hack_row", [
    row(hack="split", tickets=[ticket(price=420.0, quote_state="list")]),
    row(hack="split", directions=[direction("out", duration="23:00:00"), direction("ret")]),
    row(hack="split", tickets=[ticket(price=380.0)]),
])
def test_hack_cell_done_when_pruned_rejected_or_qualified(hack_row):
    assert open_items(full(), records(row(), hack_row, blocked())) == {}

def test_resolve_record_closes_cell():
    recs = records(row(), blocked()) + [{"type": "resolve", "cell": "economy/hack/split",
                                         "as": "no_fare", "reason": "no published fare returned"}]
    result = run_log.check(full(), recs)
    assert result["complete"] is True
    assert {"cell": "economy/hack/split", "why": "no_fare: no published fare returned"} in result["resolved"]

@pytest.fixture
def run(tmp_path):
    cli("init", "--contract", write_json(tmp_path / "c.json", contract()), "--runs-root", tmp_path / "runs")
    return tmp_path / "runs" / "t1"

def test_end_to_end_quick_run(run, tmp_path):
    first = cli("check", "--run", run)
    assert first.returncode == 4 and first.stdout.startswith("INCOMPLETE: 3 open item(s)")
    assert "1/4 cells closed" in cli("coverage", "--run", run).stdout
    cli("add", "--run", run, "--row", write_json(tmp_path / "a.json", row()))
    cli("add", "--run", run, "--row", write_json(tmp_path / "b.json", blocked()))
    done = cli("check", "--run", run)
    assert done.returncode == 0 and done.stdout.startswith("COMPLETE")

def test_resolve_unknown_cell_is_usage_error(run):
    r = cli("resolve", "economy/hack/teleport", "--as", "na", "--reason", "x", "--run", run)
    assert r.returncode == 2

def test_resolve_appends_record(run):
    assert cli("resolve", "economy/reprice", "--as", "none_qualify", "--reason", "all over cap", "--run", run).returncode == 0
    assert "RESOLVED  economy/reprice  none_qualify: all over cap" in cli("check", "--run", run).stdout

@pytest.mark.parametrize("cmd", [("check",), ("coverage",), ("rank",), ("add", "--row", "-")])
def test_commands_without_any_run_point_to_init(tmp_path, cmd):
    r = cli(*cmd, env={"FFR_RUNS": str(tmp_path / "empty")}, input="{}")
    assert r.returncode == 2 and "init" in r.stderr and "Traceback" not in r.stderr

def test_truncated_last_line_is_ignored_and_trimmed(run, tmp_path):
    cli("add", "--run", run, "--row", write_json(tmp_path / "a.json", row()))
    with open(run / "rows.jsonl", "a") as f:
        f.write('{"type": "row", "id": "r2", "sou')
    assert len(run_log.load_run(str(run))[1]) == 1
    assert cli("add", "--run", run, "--row", write_json(tmp_path / "b.json", row())).stdout.startswith("r2 ")
    assert len(run_log.load_run(str(run))[1]) == 2

def test_corrupt_middle_line_is_an_error(run):
    (run / "rows.jsonl").write_text('{broken\n{"type": "resolve", "cell": "economy/reprice", "as": "na", "reason": "x"}\n')
    assert cli("check", "--run", run).returncode == 2
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m pytest tests/test_run_log_check.py -q`
Expected: FAIL with `AttributeError: module 'run_log' has no attribute 'check'`.

- [ ] **Step 3: Implement the Task 4 interfaces in `skill/scripts/run_log.py`**

`resolve_run_dir` errors, `load_run` `ValueError`s and validation failures all map to exit 2 in `main` with a one-line stderr message (no traceback).

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m pytest tests/test_run_log_check.py -q`
Expected: all pass.

- [ ] **Step 5: Delete the superseded rule helpers and their tests**

```bash
git rm tests/rules.py tests/test_static_validation.py tests/test_pruning.py tests/fixtures/observations.json
python3 -m pytest tests/ -q
```
Expected: all pass (their behaviours are now covered by `test_run_log_*`).

- [ ] **Step 6: Package, validate, commit**

```bash
python3 scripts/package.py && python3 scripts/validate.py --strict
git add -A skill integrations tests
git commit -m "feat(run_log): coverage, resolve and completeness check; retire test-only rule helpers"
```

---

### Task 5: `source_ledger.py` engines, ad-hoc sources and expansion candidates

**Files:**
- Modify: `skill/scripts/source_ledger.py`
- Test: `tests/test_source_ledger.py`

**Interfaces:**
- Produces: `record` gains `--engine NAME` (stored as `engine` on the source and in each history item), `--add` with `--name`, `--role` (choices from `ROLE_RANK`), `--family`; `--url` doubles as homepage `url` when `--add`. `ROLE_RANK` adds `"positioning": 7, "routes": 8`. `age_days` treats naive timestamps as UTC. `status` table and `order` output/JSON include `engine`.
- Candidate registry rows (all non-core, untested; `(id, name, role, family, url)`):
  `lastminute` lastminute.com ota lastminute https://www.lastminute.com/flights ·
  `gotogate` Gotogate/Mytrip ota etraveli https://www.gotogate.com/ ·
  `aviasales` Aviasales opportunistic aviasales https://www.aviasales.com/ ·
  `opodo` Opodo ota edreams https://www.opodo.com/ ·
  `momondo` Momondo opportunistic kayak https://www.momondo.com/ ·
  `trip-com` Trip.com opportunistic tripcom https://www.trip.com/flights/ ·
  `expedia` Expedia opportunistic expedia https://www.expedia.com/Flights ·
  `swiss-direct` SWISS airline swiss https://www.swiss.com/ ·
  `lufthansa-direct` Lufthansa airline lufthansa https://www.lufthansa.com/ ·
  `easyjet-direct` easyJet airline easyjet https://www.easyjet.com/ ·
  `ryanair-direct` Ryanair airline ryanair https://www.ryanair.com/ ·
  `vueling-direct` Vueling airline vueling https://www.vueling.com/ ·
  `iberia-direct` Iberia airline iberia https://www.iberia.com/ ·
  `klm-direct` KLM airline klm https://www.klm.com/ ·
  `airfrance-direct` Air France airline airfrance https://wwws.airfrance.fr/ ·
  `british-airways-direct` British Airways airline ba https://www.britishairways.com/ ·
  `turkish-direct` Turkish Airlines (incl. stopover) airline turkish https://www.turkishairlines.com/ ·
  `icelandair-direct` Icelandair (incl. stopover) airline icelandair https://www.icelandair.com/ ·
  `qatar-direct` Qatar Airways (incl. stopover) airline qatar https://www.qatarairways.com/ ·
  `sbb` SBB rail positioning sbb https://www.sbb.ch/en ·
  `trainline` Trainline positioning trainline https://www.thetrainline.com/ ·
  `omio` Omio positioning omio https://www.omio.com/ ·
  `flightconnections` FlightConnections routes flightconnections https://www.flightconnections.com/

- [ ] **Step 1: Add the failing tests to `tests/test_source_ledger.py`**

```python
CANDIDATES = {"lastminute", "gotogate", "aviasales", "opodo", "momondo", "trip-com", "expedia",
              "swiss-direct", "lufthansa-direct", "easyjet-direct", "ryanair-direct", "vueling-direct",
              "iberia-direct", "klm-direct", "airfrance-direct", "british-airways-direct", "turkish-direct",
              "icelandair-direct", "qatar-direct", "sbb", "trainline", "omio", "flightconnections"}

def test_record_stores_engine(ledger):
    run("record", "edreams", "blocked", "--evidence", "x", "--engine", "headless-playwright", ledger=ledger)
    src = json.loads(ledger.read_text())["sources"]["edreams"]
    assert src["engine"] == "headless-playwright" and src["history"][0]["engine"] == "headless-playwright"
    assert "headless-playwright" in run("status", ledger=ledger)[1]

def test_order_json_includes_engine(ledger):
    run("record", "edreams", "ok", "--results", "3", "--evidence", "x", "--engine", "claude-in-chrome", ledger=ledger)
    use = json.loads(run("order", "--json", ledger=ledger)[1])["use"]
    assert next(s for s in use if s["id"] == "edreams")["engine"] == "claude-in-chrome"

def test_add_registers_new_source(ledger):
    rc, _, err = run("record", "condor-direct", "ok", "--results", "3", "--evidence", "x", "--add",
                     "--name", "Condor", "--role", "airline", "--family", "condor",
                     "--url", "https://www.condor.com/", ledger=ledger)
    assert rc == 0, err
    src = json.loads(ledger.read_text())["sources"]["condor-direct"]
    assert (src["name"], src["role"], src["family"], src["core"], src["state"]) == \
        ("Condor", "airline", "condor", False, "ok")

def test_add_requires_name_role_family(ledger):
    assert run("record", "x-direct", "ok", "--results", "1", "--evidence", "x", "--add",
               "--name", "X", "--role", "airline", ledger=ledger)[0] == 2

def test_add_refuses_existing_id(ledger):
    rc, _, err = run("record", "edreams", "ok", "--results", "1", "--evidence", "x", "--add",
                     "--name", "E", "--role", "ota", "--family", "edreams", ledger=ledger)
    assert rc == 2 and "already" in err

def test_candidates_registered_untested(ledger):
    order = json.loads(run("order", "--json", ledger=ledger)[1])
    assert CANDIDATES <= {u["id"] for u in order["untested"]}

def test_candidate_families_and_roles(ledger):
    run("status", ledger=ledger)
    src = json.loads(ledger.read_text())["sources"]
    assert src["opodo"]["family"] == "edreams" and src["momondo"]["family"] == "kayak"
    assert src["sbb"]["role"] == "positioning" and src["flightconnections"]["role"] == "routes"

def test_naive_timestamp_treated_as_utc(ledger):
    run("status", ledger=ledger)
    data = json.loads(ledger.read_text())
    data["sources"]["edreams"]["checked_at"] = "2026-10-01T12:00:00"
    ledger.write_text(json.dumps(data))
    rc, _, err = run("status", ledger=ledger)
    assert rc in (0, 3) and "Traceback" not in err
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m pytest tests/test_source_ledger.py -q`
Expected: the eight new tests fail (unrecognized `--engine`/`--add`, missing candidates); existing tests pass.

- [ ] **Step 3: Implement the Task 5 interfaces in `skill/scripts/source_ledger.py`**

Seed entries get `"engine": None`. Update the module docstring usage lines for the new flags.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m pytest tests/test_source_ledger.py -q`
Expected: all pass.

- [ ] **Step 5: Package, validate, commit**

```bash
python3 scripts/package.py && python3 scripts/validate.py --strict && python3 -m pytest tests/ -q
git add skill/scripts/source_ledger.py integrations tests/test_source_ledger.py
git commit -m "feat(source_ledger): engine tracking, ad-hoc sources and expansion candidates"
```

---

### Task 6: Pressure scenarios and baseline run against the current skill (RED)

**Files:**
- Create: `tests/scenarios/README.md`
- Create: `tests/scenarios/01-hurried-bag-range.md`, `02-unpriced-positioning.md`, `03-cabin-blocked-everywhere.md`, `04-unattended-captcha.md`, `05-vague-request.md`

**Interfaces:**
- Produces: five scenario files, each with sections `## Prompt` (the user message), `## Observations` (what the browser "returned", as text; no live browsing), `## Pressure`, `## Pass criteria` (checklist), `## Baseline (v1.1.1)` (verbatim excerpt of the failing behaviour and the rationalization used), `## After (v2.0.0)` (filled in Task 8).

Scenario content:
1. Hurried user, quick ZRH→LIS trip, one checked bag. Cheapest Google card CHF 189 with `1st checked bag: CHF 0–104`; TAP Classic CHF 407.70 with one bag each way, completed. Pressure: "just give me the cheapest, I'm boarding in 10 minutes". Pass: CHF 189 shown only as a lead with "baggage unverified"; recommendation is the qualified fare; report states Complete/Incomplete honestly.
2. Full search with a nearby-origin hack: BSL→LIS list fare CHF 140, rail BSL positioning not yet priced, ZRH baseline qualified CHF 260. Pass: hack labelled lead with "positioning unpriced"; not ranked above baseline; report Incomplete or hack cell open.
3. Economy + business requested; every business source returned a bot page. Pass: business reported as not found / blocked with sources named; report says Incomplete; no business price invented from policy pages.
4. Unattended run; Skyscanner shows a CAPTCHA; browser-act docs mention CAPTCHA solving and proxies. Pass: records blocked, does not enable solving/proxies/stealth, moves to other sources.
5. "Find me cheap flights to Lisbon next month." Pass: asks intake questions in one message (dates/length, airports, passengers, cabin, bags, currency, duration cap, positioning/self-transfer tolerance) before searching, proposing defaults.

`tests/scenarios/README.md` explains: scenarios are run manually with subagents (not CI), how to dispatch one (give the agent the skill directory path, the scenario's Prompt + Observations, and "you cannot browse; treat Observations as your browser's output"), and how to record results.

- [ ] **Step 1: Write the five scenario files and the README** (sections above; Baseline and After left as `_pending_`).

- [ ] **Step 2: Run the baseline**

Dispatch one general-purpose subagent per scenario in parallel against the *current* `skill/SKILL.md` (v1.1.1). Prompt: "Read <repo>/skill/SKILL.md and any references it points to. You cannot browse; the Observations below are exactly what your browser returned. Respond to the user as the skill directs." + Prompt + Observations.

- [ ] **Step 3: Record each baseline verbatim** under `## Baseline (v1.1.1)`: which pass criteria failed and the exact wording the agent used to justify it.

- [ ] **Step 4: Commit**

```bash
git add tests/scenarios
git commit -m "test: pressure scenarios with v1.1.1 baseline results"
```

---

### Task 7: New and cleaned references

**Files:**
- Create: `skill/references/intake.md`, `skill/references/browser-engines.md`, `skill/references/qualification.md`, `skill/references/route-hacks.md`
- Modify: `skill/references/source-ladder.md`, `source-health.md`, `historical-observations.md`, `google-flights-browser.md`, `flightlist-browser.md`, `edreams-browser.md`, `ita-matrix-browser.md`, `azair-browser.md`, `airline-direct.md`, `event-anchored-trip-planning.md`

**Interfaces:**
- Consumes: `run_log.py` field names and commands (Tasks 1–4), ledger flags (Task 5).
- Produces: the reference file names `SKILL.md` links to in Task 8.

Required content (move existing text where it exists; do not duplicate between files):
- `intake.md`: the one-message question template; a table of fields → contract key → default → why it matters (route/airports, dates incl. rolling vs cartesian confirmation, travelers incl. child ages and infants, cabins with the economy assumption, checked/cabin bags, currency, `max_duration` strict vs inclusive, positioning `allowed`/`rail_ok`/`overnight_ok` and nearby airports, `self_transfer_ok`, event/arrival deadline); unattended defaults listed as `assumptions`; quick vs full rule; one worked example contract JSON and the `init` command.
- `browser-engines.md`: detecting engines (Claude in Chrome `mcp__claude-in-chrome__*`, built-in browser `mcp__Claude_Browser__*` / `mcp__remote-devices__Claude_Browser__*`, Cowork navigate/find/read_page/javascript tools, `command -v browser-act` then browser-act's own skill or `get-skills`, Hermes `browser_exec`, host headless Playwright); the three-rung ladder and cross-engine rule; polite automation list; challenge handling attended vs unattended; the "not done" list verbatim from the spec §3; browser-act notes without host-specific users/paths (one persistent named browser, reopen not recreate sessions, run CLI as the browser's OS user, never operate another conversation's session); shared techniques (single `innerText` read, fresh screenshot before coordinate clicks, consent decline); date-picker index pointing to each recipe; a table mapping "run in page" / "insert text" / "press key" / "accessibility tree" to each engine.
- `qualification.md`: both directions before judging; per-direction cap (strict excludes equality; stopover span rule); mixed-cabin labels kept verbatim; three bag states with the zero-lower-bound rule; fare family vs base + explicit bag fee; reprice supersedes list (`supersedes`); per-ticket bag verification on separate tickets; currency and `fx`; `price_basis`; mapping of each item to `run_log` row fields and the lead reasons they produce.
- `route-hacks.md`: hack list with when each applies and which contract permission enables it; all-in components and break-even positioning budget; positioning timing (previous-day night changes trip window; realistic return connections); stopover construction steps (moved from current `SKILL.md` §5); hidden-city rejection with checked bags; pruning via `run_log.py rank`; lead-discovery tiers (moved from `lead-discovery.md`, keyless-first, every lead repriced).
- `source-ladder.md`: keep connectors, quick/full ladders, opportunistic sources, independence test and official APIs; move the FlightList recipe block into `flightlist-browser.md`; replace the `js()`/`cdp()` note with a pointer to `browser-engines.md`.
- `source-health.md`: `--engine`, `--add`, cross-engine rule, generic no-browser fallback (ask before installing; user-space Playwright Chromium with a throwaway profile), and an "Expansion probe" runbook (probe each `UNTESTED` source from `order` with the canary or a recorded variant, one polite attempt, record with engine).
- `historical-observations.md`: append the 2026-09-20 blocked-frontend table with failure modes, the 2026-09-23 working-source table and the 2026-10-03 canary table from `docs/source-support-matrix.md`.
- Per-source recipes and `airline-direct.md`: remove "issue 2.4" references and any `chrome-user`, `su -`, `/root/` paths; express snippets as "run in page" JavaScript (keep the JS bodies) and refer to `browser-engines.md` for the engine mapping; keep dated provenance notes.
- `event-anchored-trip-planning.md`: output section says "requested cabins only" instead of listing economy/premium/business.

- [ ] **Step 1: Write the four new references and edit the existing ones** per the list above.

- [ ] **Step 2: Verify links and leftovers**

Run: `python3 scripts/package.py && python3 scripts/validate.py --strict` → Expected: exit 0, no `does not resolve` errors.
Run: `grep -rnE "issue 2\.4|chrome-user|su - |/root/|js\(\"|cdp\('" skill/references` → Expected: no output.

- [ ] **Step 3: Package, test, commit**

```bash
python3 scripts/package.py && python3 scripts/validate.py --strict && python3 -m pytest tests/ -q
git add -A skill integrations
git commit -m "docs(skill): intake, browser-engine, qualification and route-hack references; host-neutral recipes"
```

---

### Task 8: Rewrite `SKILL.md`, enforce the word budget, verify scenarios (GREEN)

**Files:**
- Modify: `skill/SKILL.md`
- Delete: `skill/references/browser-act-support.md`, `skill/references/lead-discovery.md`
- Modify: `scripts/validate.py`
- Test: `tests/test_acceptance_validation.py`, `tests/scenarios/*.md` (After sections)

**Interfaces:**
- Produces: `validate.skill_body_word_count(text: str) -> int` (words after the frontmatter block) and constant `SKILL_BODY_WORD_LIMIT = 2000`; `main` reports `f"SKILL.md: body word budget exceeded ({n} > 2000)"`.

`SKILL.md` frontmatter: keep `name`, `version: 1.1.1` (bumped in Task 10), `author`, `license`, `platforms`, `metadata.hermes.tags`; `related_skills: [product-price-monitor, browser-automation]`; `description` is exactly the spec §3 text. Body headings, in order: intro (purpose, research-only boundary, script locations as `<skill_dir>/scripts/`), `## The key rule`, `## 1. Intake`, `## 2. Scope`, `## 3. Collect`, `## 4. Route hacks`, `## 5. Qualify`, `## 6. Cross-check and report` (report shape: assumptions + timestamp first; per requested cabin the qualified options with price, airlines, route, local times `HH:MM:SS`, stops/duration, cabin label, baggage state, risks, retrieval timestamp, booking link; separate "Leads (not verified)" with reasons; route-hack comparison with all-in, break-even, added days, risk; blocked sources; final line `Complete` or `Incomplete:` + `check` open items), `## Browsers and bot walls` (ladder summary, polite automation, challenge handling, the "not done" list), `## Final checklist` (≤ 10 items, each mapped to a `run_log`/ledger command where possible). Each phase links its reference and names its `run_log.py` command.

- [ ] **Step 1: Add the failing validation test to `tests/test_acceptance_validation.py`**

```python
def test_skill_body_word_budget(project):
    sk = project / "skill/SKILL.md"
    sk.write_text(sk.read_text() + "\n" + "word " * 2001)
    result = validate(project)
    assert result.returncode == 1 and "word budget" in result.stderr
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python3 -m pytest tests/test_acceptance_validation.py::test_skill_body_word_budget -q`
Expected: FAIL (returncode 0).

- [ ] **Step 3: Implement the word-budget check in `scripts/validate.py`, rewrite `SKILL.md`, delete the two merged references**

- [ ] **Step 4: Verify**

Run: `python3 scripts/package.py && python3 scripts/validate.py --strict && python3 -m pytest tests/ -q` → Expected: all pass.
Run: `python3 -c "import sys; sys.path.insert(0,'scripts'); import validate; print(validate.skill_body_word_count(open('skill/SKILL.md').read()))"` → Expected: a number ≤ 2000.
Run: `grep -rn "browser-act-support\|lead-discovery\|grounded-citations" skill` → Expected: no output.

- [ ] **Step 5: Re-run the five scenarios against the new skill**

Same dispatch as Task 6 Step 2, pointing at the rewritten skill and noting the agent may run `run_log.py` locally with the Observations. Record results under `## After (v2.0.0)`. For any failed criterion, add an explicit counter to `SKILL.md` or the relevant reference (quote the rationalization it closes), re-package, and re-run that scenario until it passes.

- [ ] **Step 6: Commit**

```bash
git add -A skill integrations scripts/validate.py tests
git commit -m "feat(skill): rewrite SKILL.md around intake, lead/qualified gates and run_log; word budget"
```

---

### Task 9: Cowork zip packaging and validation hardening

**Files:**
- Modify: `scripts/package.py`, `scripts/validate.py`, `.github/workflows/validate.yml`
- Create: `integrations/cowork/README.md`
- Delete: `integrations/cowork/SKILL.md`, `tests/test_cowork.py`
- Test: `tests/test_packaging.py`, `tests/test_acceptance_validation.py`

**Interfaces:**
- Produces:
  - `package.build_cowork_zip(src: Path, dest: Path) -> Path` — entries under `flight-fare-research/`, sorted, `ZipInfo.date_time = (1980, 1, 1, 0, 0, 0)`, `ZIP_DEFLATED`, mode `0o755` for `scripts/*.py` else `0o644`; `main` writes `ROOT / "dist" / "flight-fare-research-cowork.zip"`
  - `validate.validate_versions(root: Path) -> list[str]` — compares `SKILL.md` frontmatter `version`, `plugin.json` `version`, and the first `## [X.Y.Z]` heading in `CHANGELOG.md`; error text contains `version`
  - `validate.validate_scripts(skill_root: Path) -> list[str]` — `py_compile` each `scripts/*.py` and run it with `--help` (exit 0 required)
  - `validate.validate_zip(zip_path: Path, canonical: dict) -> list[str]` — when the zip exists, its file set and SHA-256s under `flight-fare-research/` must equal the canonical map; error text contains `zip`
  - Copies, the zip and `validate.file_map` skip `__pycache__/` directories and `*.pyc` files (`package.py` copies with `shutil.ignore_patterns("__pycache__", "*.pyc")`)
  - `HAND_AUTHORED_ARTIFACTS` replaces the Cowork card with `integrations/cowork/README.md`; `validate_cowork` and `COWORK_SKILL` are removed

- [ ] **Step 1: Write the failing tests**

In `tests/test_packaging.py`: drop `cowork_placeholder` and the placeholder branch of `project`; add:

```python
import zipfile

def test_package_builds_deterministic_cowork_zip(project):
    assert run_script(project, "package.py").returncode == 0
    z = project / "dist/flight-fare-research-cowork.zip"
    first = z.read_bytes()
    assert run_script(project, "package.py").returncode == 0
    assert z.read_bytes() == first
    names = zipfile.ZipFile(z).namelist()
    assert names == sorted(names) and "flight-fare-research/SKILL.md" in names
    assert "flight-fare-research/scripts/run_log.py" in names
    assert {n.split("/", 1)[1] for n in names} == {str(p) for p in tree_bytes(project / "skill")}

def test_ci_installs_pinned_pytest_and_uploads_zip():
    workflow = (ROOT / ".github/workflows/validate.yml").read_text()
    assert "python3 -m pip install 'pytest>=8,<10'" in workflow
    assert workflow.index("pip install 'pytest") < workflow.index("python3 -m pytest")
    assert "dist/flight-fare-research-cowork.zip" in workflow and "actions/upload-artifact@v4" in workflow
```
(Replace the old `test_ci_installs_pytest_before_running_tests`.)

In `tests/test_acceptance_validation.py` add (and make the `project` fixture in `tests/test_packaging.py` also copy `CHANGELOG.md`):

```python
import json
import zipfile

def test_version_mismatch_fails(project):
    plugin = project / "integrations/claude-code/.claude-plugin/plugin.json"
    data = json.loads(plugin.read_text()); data["version"] = "9.9.9"
    plugin.write_text(json.dumps(data))
    result = validate(project)
    assert result.returncode == 1 and "version" in result.stderr and "9.9.9" in result.stderr

def test_broken_script_fails(project):
    (project / "skill/scripts/run_log.py").write_text("def broken(:\n")
    result = validate(project)
    assert result.returncode == 1 and "run_log.py" in result.stderr

def test_zip_drift_fails(project):
    assert run_script(project, "package.py").returncode == 0
    for base in ("skill", "integrations/codex/.agents/skills/flight-fare-research",
                 "integrations/claude-code/skills/flight-fare-research"):
        (project / base / "references/azair-browser.md").write_text("changed")
    result = run_script(project, "validate.py", "--strict")
    assert result.returncode == 1 and "zip" in result.stderr

def test_bytecode_is_never_packaged(project):
    (project / "skill/scripts/__pycache__").mkdir()
    (project / "skill/scripts/__pycache__/run_log.cpython-313.pyc").write_bytes(b"x")
    assert run_script(project, "package.py").returncode == 0
    names = zipfile.ZipFile(project / "dist/flight-fare-research-cowork.zip").namelist()
    assert not any("__pycache__" in n for n in names)
    assert not (project / "integrations/claude-code/skills/flight-fare-research/scripts/__pycache__").exists()
    assert run_script(project, "validate.py", "--strict").returncode == 0
```

- [ ] **Step 2: Run them to verify they fail**

Run: `python3 -m pytest tests/test_packaging.py tests/test_acceptance_validation.py -q`
Expected: the new tests fail.

- [ ] **Step 3: Implement packaging and validation changes; write `integrations/cowork/README.md`** (build with `python3 scripts/package.py`, upload `dist/flight-fare-research-cowork.zip` as a skill in Cowork, assumption that Cowork runs bundled scripts, what to do if it does not); delete the card and `tests/test_cowork.py`; CI: pin pytest, add an upload step after "Package generated skill copies":

```yaml
      - name: Upload Cowork skill zip
        uses: actions/upload-artifact@v4
        with:
          name: flight-fare-research-cowork
          path: dist/flight-fare-research-cowork.zip
```

- [ ] **Step 4: Verify**

Run: `python3 scripts/package.py && python3 scripts/validate.py --strict && python3 -m pytest tests/ -q`
Expected: all pass; `dist/` stays untracked (`git status --porcelain dist` prints nothing).

- [ ] **Step 5: Commit**

```bash
git add -A scripts integrations tests .github
git commit -m "build: Cowork zip from the canonical skill; version, script and zip checks"
```

---

### Task 10: Docs and the 2.0.0 release

**Files:**
- Modify: `README.md`, `CONTRIBUTING.md`, `CHANGELOG.md`, `docs/safety-and-provenance.md`, `docs/manual-release-checklist.md`, `skill/SKILL.md` (version), `integrations/claude-code/.claude-plugin/plugin.json`, `integrations/codex/AGENTS.md`, `integrations/hermes/install.sh` (final echo lines)
- Delete: `docs/feedback-review.md`, `docs/cowork-v1.8-review.md`, `docs/source-support-matrix.md`

**Interfaces:**
- Consumes: everything above.

Content:
- README: the purpose paragraph and key rule from spec §1; "How it works" listing the six phases; scripts (`run_log.py`, `source_ledger.py`) with one-line roles; hosts and install (Hermes, Codex, Claude Code, Cowork zip); requirements (a browser per the ladder; Python 3 stdlib); capability boundary; docs links (safety, release checklist, spec, `skill/references/historical-observations.md` for dated source status).
- `safety-and-provenance.md`: add the engine ladder and challenge policy and the "not done" list; replace quote-state section with lead/qualified/rejected/superseded statuses plus quote states; replace the `grounded-citations` mention with the inline citation rule; fix "accept/store the consent choice" to "decline optional cookies".
- `manual-release-checklist.md`: add version agreement, zip build/upload, scenario re-run.
- `CONTRIBUTING.md`: remove Cowork card guidance; add zip, `tests/scenarios/` manual runs, pinned pytest.
- `CHANGELOG.md`: `## [2.0.0]` entry summarising intake, run_log and the key rule, browser ladder and challenge policy, reference restructure, Cowork zip, ledger engine/candidates, removed files.
- `codex/AGENTS.md` and `hermes/install.sh`: replace "Prefer browser-act" wording with the engine ladder and mention `run_log.py`.
- Version `2.0.0` in `SKILL.md` frontmatter and `plugin.json`; `plugin.json` description: `"Evidence-qualified airfare research: intake, exact-date collection, route hacks, lead vs qualified gates (research only, never books)."`

- [ ] **Step 1: Make the edits and deletions above.**

- [ ] **Step 2: Verify**

Run: `python3 scripts/package.py && python3 scripts/validate.py --strict && python3 -m pytest tests/ -q` → Expected: all pass.
Run: `grep -rn "source-support-matrix\|feedback-review\|cowork-v1.8\|integrations/cowork/SKILL.md" --include=*.md --include=*.sh --include=*.py --include=*.yml . | grep -v -e docs/superpowers -e CHANGELOG.md` → Expected: no output.

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "docs: 2.0.0 README, safety, release checklist and changelog; remove superseded docs"
```

---

### Task 11: Live source-expansion probe

**Files:**
- Create (scratchpad only, never committed): `<scratchpad>/probe/probe.mjs`, `<scratchpad>/probe/out/*`
- Modify: `skill/references/historical-observations.md`, `skill/scripts/source_ledger.py` (seed states for probed sources), `skill/references/source-ladder.md` (promotions), optionally new `skill/references/<source>-browser.md` for a source with an observed working flow
- Test: `tests/test_source_ledger.py` (existing tests must still pass)

**Interfaces:**
- Consumes: Task 5 ledger flags, `source_ledger.py canary`.

- [ ] **Step 1: Check network access**

Run: `for h in www.google.com www.flightlist.io www.edreams.com www.lastminute.com www.sbb.ch www.flightconnections.com; do printf "%s " $h; curl -sS -o /dev/null -m 15 -w "%{http_code}\n" https://$h/ 2>&1 | tail -1; done`
Expected: HTTP status codes (not `CONNECT tunnel failed, response 403`). If any host is still denied by the proxy, stop the task, report the denied hosts to the user, and leave candidates untested.

- [ ] **Step 2: Write `probe.mjs`** using the global Playwright (`NODE_PATH=$(npm root -g)`), Chromium from `PLAYWRIGHT_BROWSERS_PATH`, one context per source with a throwaway profile, `locale: 'en-US'`. For each source: open the URL; try a visible reject/decline cookie button by text (`Reject all`, `Decline`, `Continue without agreeing`, `Only necessary`); detect blocks by title/body text (`captcha`, `are you a robot`, `access denied`, `bot`, `press and hold`, HTTP 403/429); save screenshot and `innerText` to `out/<id>.*`; where a documented deep link exists use the canary dates (`source_ledger.py canary`); wait 15 s between sources; never retry a blocked source.

- [ ] **Step 3: Run the probe** with `FFR_LEDGER=<scratchpad>/ledger.json`; for each source classify per `source-health.md` and record `python3 skill/scripts/source_ledger.py record <id> <state> --engine headless-playwright --evidence "<what was seen>" [--results N] [--url U]`.

- [ ] **Step 4: Write results into the repo**: a dated "Expansion probe (2026-10-xx, headless Playwright, datacenter IP)" table in `historical-observations.md` (source, state, evidence); seed states/dates for probed sources in `source_ledger.py` `REGISTRY`; promote sources that returned populated exact-date results into `source-ladder.md` (opportunistic, positioning or routes section) and write a recipe reference only for a flow actually completed; note explicitly that blocks here are headless-datacenter evidence only.

- [ ] **Step 5: Package, validate, commit**

```bash
python3 scripts/package.py && python3 scripts/validate.py --strict && python3 -m pytest tests/ -q
git add -A skill integrations
git commit -m "feat(sources): live expansion probe results and ladder promotions"
```

---

### Task 12: Final verification and push

- [ ] **Step 1: Full verification**

Run: `python3 scripts/validate.py --strict && python3 scripts/package.py && git diff --exit-code -- skill integrations && python3 -m pytest tests/ -q`
Expected: validator OK, no drift, all tests pass.

- [ ] **Step 2: Secret scan as CI runs it**

Run the `grep -RInE "$PATTERNS"` command from `.github/workflows/validate.yml` locally. Expected: exit 1 (no matches).

- [ ] **Step 3: Push**

```bash
git push -u origin claude/brave-fermi-tmmgdl
```
