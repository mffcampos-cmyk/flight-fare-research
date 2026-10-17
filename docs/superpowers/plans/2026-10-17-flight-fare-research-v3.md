# Flight Fare Research 3.0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship version 3.0.0 of the skill: a leg-based contract with airport groups and region discovery, a fixed intake questionnaire, BrowserAct as the first-choice engine with a login check and challenge policy, sweeps for FlightList and Google, a job planner, and `dist/` packaging.

**Architecture:** The skill stays an agent workflow plus standard-library Python scripts that keep the books and drive BrowserAct sessions. `run_log.py` is split into two importable modules (`ffr_contract.py` for the contract, tuples and cells; `ffr_rows.py` for rows, gates, ranking and completeness) and a thin CLI. A new `browseract.py` wraps the `browser-act` CLI so every sweep shares one driver, one login check and one challenge policy. Host packages are built into `dist/` instead of being committed.

**Tech Stack:** Python 3.12+ standard library only (scripts and validator); pytest for tests; the `browser-act` CLI 1.4.3 at runtime (never in tests: tests use a fake CLI on `PATH`).

**Spec:** `docs/superpowers/specs/2026-10-17-flight-fare-research-v3-design.md`

## Global Constraints

- Scripts, validator and packager use the Python standard library only; no network in scripts or tests.
- `skill/SKILL.md` body stays at or under 2,000 words (`validate.py` enforces it).
- Version `3.0.0` in `skill/SKILL.md` frontmatter, `integrations/claude-code/.claude-plugin/plugin.json` and the top `CHANGELOG.md` heading.
- Every backtick `*.md` reference inside `skill/` must resolve (`validate.py`).
- Never write `__pycache__` into `skill/` (scripts set `sys.dont_write_bytecode = True`; tests do too).
- No credentials, cookies, booking tokens or run/ledger files in the repo; CI scans for them.
- Scripts exit 0 on success, 2 on usage or validation errors, 4 for `check` while incomplete, 3 for a sweep stopped by a challenge.
- The agent never creates the BrowserAct account, never pastes a key into chat, never buys proxies or browsers, never books.
- Commit after every task; `python3 scripts/validate.py --strict` and the full test suite must pass before the final push.

## Review Focus

1. A contract whose `after_leg` references a later leg, or a leg date earlier than the previous leg's, must be refused by `init` with a message naming the leg (Task 2).
2. A fare row from Basel (a `via: rail` airport) with no ground row for that date stays a lead with `ground unpriced (BSL)`; a ground row dated the day before counts only when `overnight_ok` is true (Task 5).
3. `browseract.py status` with the CLI missing, the CLI present but no key, and the CLI present with a key in `BROWSERACT_API_KEY` must each produce the documented JSON without raising; a stale cache older than 24 hours is ignored (Task 7).
4. `handle_challenge` must never call `solve-captcha` twice on one page and must record `blocked` when neither a key nor a reachable user exists (Task 7).
5. In `fast` mode, `check` must stay incomplete while a region group has no shortlist, and a `confirm` cell must not close on discovery-phase rows alone (Tasks 3 and 5).

---

### Task 1: Build host packages into `dist/`

**Files:**
- Modify: `scripts/package.py`, `scripts/validate.py`
- Modify: `.github/workflows/validate.yml`, `README.md`, `CONTRIBUTING.md`, `docs/manual-release-checklist.md`, `integrations/cowork/README.md`
- Create: `requirements-dev.txt`
- Delete: `integrations/claude-code/skills/`, `integrations/codex/.agents/`
- Test: `tests/test_packaging.py`, `tests/test_acceptance_validation.py`

**Interfaces:**
- Produces: `package.py` writes `dist/claude-code/` (`.claude-plugin/plugin.json` copied from `integrations/claude-code/`, `skills/flight-fare-research/` from `skill/`), `dist/codex/` (`AGENTS.md` copied from `integrations/codex/`, `.agents/skills/flight-fare-research/`), and `dist/flight-fare-research-cowork.zip`. `validate.py` checks `dist/` trees and the zip only when they exist, and skips `--help` for `skill/scripts/ffr_*.py` library modules.

- [ ] **Step 1: Rewrite the packaging tests**

In `tests/test_packaging.py`, point the `project` fixture at `scripts`, `skill`, `integrations` and `CHANGELOG.md` as now, and replace the tests that read `integrations/.../skills/` with:

```python
def test_package_builds_dist_trees_and_zip(project):
    result = run_script(project, "package.py")
    assert result.returncode == 0, result.stderr
    assert (project / "dist/claude-code/.claude-plugin/plugin.json").is_file()
    assert (project / "dist/claude-code/skills/flight-fare-research/SKILL.md").is_file()
    assert (project / "dist/codex/AGENTS.md").is_file()
    assert (project / "dist/codex/.agents/skills/flight-fare-research/scripts/run_log.py").is_file()
    assert zipfile.ZipFile(project / "dist/flight-fare-research-cowork.zip").namelist()[0].startswith("flight-fare-research/")

def test_package_is_repeatable_and_removes_stale_files(project):
    run_script(project, "package.py")
    stale = project / "dist/claude-code/skills/flight-fare-research/stale.txt"
    stale.write_text("stale")
    run_script(project, "package.py")
    assert not stale.exists()

def test_validate_passes_without_dist_and_fails_on_stale_dist(project):
    assert run_script(project, "validate.py", "--strict").returncode == 0
    run_script(project, "package.py")
    (project / "skill/references/intake.md").write_text("changed\n")
    result = run_script(project, "validate.py", "--strict")
    assert result.returncode != 0 and "dist" in result.stderr
```

Keep the existing tests for a missing `SKILL.md`, the word budget, version agreement and `--help`; change their paths from `integrations/.../skills/` to `dist/...`.

- [ ] **Step 2: Run the packaging tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_packaging.py tests/test_acceptance_validation.py -q`
Expected: FAIL (dist paths missing).

- [ ] **Step 3: Implement `package.py` and `validate.py` changes**

`package.py`: `DESTINATIONS` becomes `dist/claude-code/skills/flight-fare-research` and `dist/codex/.agents/skills/flight-fare-research`; add `copy_hand_authored()` copying `integrations/claude-code/.claude-plugin/plugin.json` and `integrations/codex/AGENTS.md` into `dist/`; remove the `dist/` tree before building.
`validate.py`: `GENERATED_TARGETS` point into `dist/`; `validate_target` returns `[]` when the target directory is absent; `validate_scripts` skips names starting with `ffr_`; keep every other check.

- [ ] **Step 4: Delete the committed copies, add `requirements-dev.txt` (`pytest>=8,<10`), update docs and CI**

`git rm -r integrations/claude-code/skills integrations/codex/.agents`. README install lines: `claude --plugin-dir dist/claude-code`, `cd dist/codex && codex`, Cowork zip path unchanged. CONTRIBUTING: `pip install -r requirements-dev.txt`; remove "commit the regenerated copies". CI: drop the "packaging drift" step; upload `dist/` as artifact `flight-fare-research-dist` in addition to the zip.

- [ ] **Step 5: Run the suite and validator**

Run: `.venv/bin/python -m pytest tests/ -q && python3 scripts/validate.py --strict && python3 scripts/package.py && python3 scripts/validate.py --strict`
Expected: all pass; `dist/` built; validator OK with `dist/` present.

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "build: host packages are built into dist/, not committed"
```

---

### Task 2: Contract v3 — legs, groups, dates, tuples

**Files:**
- Create: `skill/scripts/ffr_contract.py`
- Test: `tests/test_contract_v3.py`
- Modify: `tests/run_log_helpers.py` (new builders)

**Interfaces:**
- Produces (in `ffr_contract.py`):
  - `UsageError` (moved here from `run_log.py`; `run_log.UsageError` stays an alias), `CABINS`, `HACKS = ("split", "open_jaw", "stopover")`, `SCOPES`, `SPEEDS = ("fast", "thorough")`, `VIA = ("rail", "bus", "flight", "car")`, `THOROUGH_TUPLE_CAP = 200`
  - `validate_contract(contract: dict) -> list[str]`
  - `normalize_contract(contract: dict) -> dict`: every leg's `from`/`to` becomes an explicit group dict (`{"name", "region", "airports": [{"code", "via", "overnight_ok"}]}`), `shape` added (`one_way`/`return`/`multi_city`), defaults filled (`speed`, `max_stops: None`, `time_windows: []`, `airlines: {"prefer": [], "exclude": []}`, `hacks` with the three booleans, `positioning`, `budget`, `shortlist: 4`, `event`, `assumptions`, travellers, bags), `via` airports dropped when `positioning.allowed` is false, every hack false under `quick`.
  - `trip_shape(legs: list[dict]) -> str`
  - `expand_tuples(contract: dict) -> list[list[str]]` sorted, one ISO date per leg.
  - `airports(group: dict) -> list[str]`, `home_airport(group) -> str`, `via_airports(contract) -> dict[str, dict]` (code → airport entry).
- Helpers in `tests/run_log_helpers.py`: `contract_v3(**over)` (two-leg return ZRH→ZZZ, fixed dates 2027-02-03 / 2027-02-17, economy, 1 bag, CHF, cap 20:00:00 inclusive, `speed: "thorough"`), `group(*codes, **over)`, `leg(frm, to, dates)`.

- [ ] **Step 1: Write the failing tests**

```python
def test_shape_is_derived():
    assert ffr_contract.trip_shape([leg("ZRH", "BKK", {"fixed": "2027-02-03"})]) == "one_way"
    assert ffr_contract.trip_shape(contract_v3()["legs"]) == "return"
    assert ffr_contract.trip_shape([leg("ZRH","BKK",{"fixed":"2027-02-03"}), leg("BKK","SIN",{"fixed":"2027-02-10"}), leg("SIN","ZRH",{"fixed":"2027-02-17"})]) == "multi_city"

def test_group_reference_resolves_and_reverses():
    c = ffr_contract.normalize_contract(contract_v3())
    assert c["legs"][1]["from"]["airports"][0]["code"] == "ZZZ"
    assert c["legs"][1]["to"]["airports"][0]["code"] == "ZRH"

@pytest.mark.parametrize("dates,count,first", [
    ({"range": {"from": "2027-02-01", "to": "2027-02-03"}}, 3, ["2027-02-01", "2027-02-15"]),
    ({"flex": {"date": "2027-02-02", "minus": 1, "plus": 1}}, 3, ["2027-02-01", "2027-02-15"]),
])
def test_tuples_from_range_and_flex_with_linked_return(dates, count, first):
    c = contract_v3(); c["legs"][0]["dates"] = dates
    c["legs"][1]["dates"] = {"after_leg": {"leg": 1, "min_days": 14, "max_days": 14}}
    assert ffr_contract.expand_tuples(ffr_contract.normalize_contract(c))[0] == first
    assert len(ffr_contract.expand_tuples(ffr_contract.normalize_contract(c))) == count

def test_after_leg_range_multiplies_tuples():  # 2 outbound dates x trip lengths 12..13 -> 4 tuples

def test_tuple_dates_must_not_go_backwards():  # fixed leg 2 before leg 1 -> error names "leg 2"

def test_after_leg_may_not_reference_a_later_leg():  # error names "leg 1"

def test_thorough_refuses_more_than_200_tuples():  # range 2027-02-01..03-31 x after_leg 10..20 -> error mentions "200"

def test_fast_mode_has_no_tuple_cap():

def test_via_airport_dropped_when_positioning_not_allowed():
    c = contract_v3(positioning={"allowed": False, "overnight_ok": False})
    c["legs"][0]["from"] = group("ZRH", {"code": "BSL", "via": "rail"})
    n = ffr_contract.normalize_contract(c)
    assert ffr_contract.airports(n["legs"][0]["from"]) == ["ZRH"]

def test_quick_scope_rules():  # quick + range dates -> error; quick + hacks on -> normalized all false

def test_region_group_without_airports_needs_fast_mode():  # thorough -> error; fast -> ok

@pytest.mark.parametrize("field,value,fragment", [
    ("max_stops", -1, "max_stops"), ("time_windows", [{"leg": 9}], "leg 9"),
    ("airlines", {"prefer": "LX"}, "airlines"), ("budget", "cheap", "budget"),
    ("hacks", {"split": "yes"}, "hacks"), ("shortlist", 0, "shortlist"),
])
def test_field_validation(field, value, fragment):

def test_split_and_open_jaw_need_a_return_trip():  # one-way + hacks split true -> normalized false with auto reason in cells (Task 3) ; here: validate ok
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_contract_v3.py -q`
Expected: FAIL with `ModuleNotFoundError: ffr_contract`.

- [ ] **Step 3: Implement `ffr_contract.py`**

Copy `duration_to_seconds`, `_is_date`, `RUN_ID`, `HHMMSS` from `run_log.py`. `expand_tuples`: recursive product over legs; for `after_leg`, candidate dates are `tuple[leg-1] + d` for `d` in `min_days..max_days`; drop tuples where any date precedes the previous leg's date. Error messages name the leg number (`leg 2: date 2027-02-01 is before leg 1`).

- [ ] **Step 4: Run to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_contract_v3.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add skill/scripts/ffr_contract.py tests/test_contract_v3.py tests/run_log_helpers.py
git commit -m "feat(contract): legs, airport groups, date tuples (v3)"
```

---

### Task 3: Cells per speed mode, shortlist and confirm

**Files:**
- Modify: `skill/scripts/ffr_contract.py`
- Test: `tests/test_cells_v3.py`

**Interfaces:**
- Produces:
  - `build_cells(contract: dict) -> list[dict]`; cell ids: `{cabin}/baseline/{ORIG}-{DEST}/{d1_d2…}` (thorough), `{cabin}/discover/{DEST}` and `{cabin}/confirm/{DEST}` (fast, with `"tuples": []` on confirm cells), `{cabin}/hack/{split|open_jaw|stopover}`, `{cabin}/crosscheck`, `{cabin}/reprice`; each cell has `kind`, `cabin`, `auto` (`{"as": "na", "reason"}` or None) and, for baseline, `origin`, `destination`, `dates`.
  - `region_groups(contract) -> list[tuple[int, str]]` (leg index, side) of groups with `region: true` and no airports.
  - `apply_shortlist(contract: dict, codes: list[str]) -> dict`: adds the codes to every empty region group (and its reversed reference), rebuilds `cells` and `date_tuples`.
  - `fill_confirm_cells(contract: dict, picks: dict[str, list[list[str]]]) -> dict`: sets `tuples` on each `{cabin}/confirm/{DEST}` from `picks[f"{cabin}/{DEST}"]`.

- [ ] **Step 1: Write the failing tests**

```python
def test_thorough_cells_per_origin_destination_tuple():
    c = contract_v3(); c["legs"][0]["from"] = group("ZRH", {"code": "BSL", "via": "rail"})
    ids = [x["id"] for x in ffr_contract.build_cells(ffr_contract.normalize_contract(c))]
    assert "economy/baseline/ZRH-ZZZ/2027-02-03_2027-02-17" in ids
    assert "economy/baseline/BSL-ZZZ/2027-02-03_2027-02-17" in ids
    assert ids[-2:] == ["economy/crosscheck", "economy/reprice"]

def test_fast_cells_are_discover_and_confirm_per_destination():
    c = contract_v3(speed="fast"); c["legs"][0]["to"] = group("BKK", "SIN")
    kinds = {(x["kind"], x.get("destination")) for x in ffr_contract.build_cells(ffr_contract.normalize_contract(c))}
    assert ("discover", "BKK") in kinds and ("confirm", "SIN") in kinds and ("baseline", None) not in kinds

def test_hack_cells_follow_the_hacks_object_and_trip_shape():
    # return + split true -> cell with auto None; one-way + split true -> auto na "one-way trip"; stopover false -> no cell

def test_region_group_yields_no_cells_until_shortlist():
    c = contract_v3(speed="fast"); c["legs"][0]["to"] = {"name": "SE Asia", "region": True, "airports": []}
    n = ffr_contract.normalize_contract(c)
    assert ffr_contract.region_groups(n) == [(0, "to")]
    assert not [x for x in ffr_contract.build_cells(n) if x["kind"] in ("discover", "confirm")]
    s = ffr_contract.apply_shortlist(n, ["BKK", "SIN"])
    assert ffr_contract.airports(s["legs"][1]["from"]) == ["BKK", "SIN"]
    assert "economy/discover/SIN" in [x["id"] for x in s["cells"]]

def test_fill_confirm_cells():
    # picks {"economy/BKK": [["2027-02-03","2027-02-17"]]} -> that cell's tuples set; unknown key -> ValueError
```

- [ ] **Step 2: Run to verify they fail** — `pytest tests/test_cells_v3.py -q` → FAIL (`build_cells` missing).

- [ ] **Step 3: Implement** `build_cells`, `region_groups`, `apply_shortlist`, `fill_confirm_cells` in `ffr_contract.py`. `apply_shortlist` refuses codes already present and codes that are not three uppercase letters.

- [ ] **Step 4: Run to verify they pass** — `pytest tests/test_cells_v3.py -q` → PASS.

- [ ] **Step 5: Commit** — `git commit -m "feat(contract): cells per speed mode, shortlist, confirm"`

---

### Task 4: Rows v3 — validation, gates and lead reasons

**Files:**
- Create: `skill/scripts/ffr_rows.py`
- Test: `tests/test_rows_v3.py`
- Modify: `tests/run_log_helpers.py` (`row_v3(**over)`, `leg_entry(n, **over)`, `ground(**over)`)

**Interfaces:**
- Produces (in `ffr_rows.py`):
  - `OUTCOMES`, `QUOTE_STATES`, `BAGGAGE`, `PRICE_BASES`, `PHASES = ("discover", "exact")`
  - `validate_row(row: dict, contract: dict) -> list[str]` (fare rows and attempts; fields: `source, family, engine, outcome, url, retrieved_at, cabin`; populated rows add `currency, origin, destination, dates, tickets, legs`; `phase` defaults `exact`; `hack` null or one of `HACKS`)
  - `validate_ground(row: dict, contract: dict) -> list[str]` (`kind: "ground"`, `source, engine, url, retrieved_at, from, to, date, price, currency, quote_state`)
  - `row_cell_id(row: dict, contract: dict) -> str`
  - `hard_gate_reasons(row, c) -> list[str]`, `lead_reasons(row, c, grounds: list[dict]) -> list[str]`
  - `row_status(row, contract, superseded: set[str], grounds: list[dict]) -> tuple[str, list[str]]`
  - `ground_for(row, c, grounds) -> dict[str, dict | None]` (via airport code → chosen ground record or None)
- Helpers: `row_v3()` is a populated return row ZRH→ZZZ with two leg entries and `dates: ["2027-02-03", "2027-02-17"]`; `ground()` is `{"kind": "ground", "source": "sbb", "engine": "test", "url": "…", "retrieved_at": "…+01:00", "from": "ZRH", "to": "BSL", "date": "2027-02-03", "price": 32.4, "currency": "CHF", "quote_state": "completed"}`.

- [ ] **Step 1: Write the failing tests**

```python
def test_populated_row_needs_every_contract_leg_or_is_a_lead():
    r = row_v3(legs=[leg_entry(1)])
    assert ffr_rows.row_status(r, contract_v3(), set(), []) == ("lead", ["leg 2 not selected"])

def test_multi_city_row_matches_each_leg_group():  # 3-leg contract; a row whose leg 2 goes to the wrong airport -> validate_row error "leg 2: destination not in contract"

def test_dates_must_be_a_contract_tuple():  # dates ["2027-02-04","2027-02-17"] -> "dates not in contract"

@pytest.mark.parametrize("over,reason", [
    ({"stops": 2}, "leg 1 stops 2 over max 1"),
    ({"dep": "2027-02-03T05:10:00"}, "leg 1 departs 05:10 before 06:00"),
    ({"airlines": ["FR"]}, "leg 1 airline FR excluded"),
])
def test_hard_gates_stops_windows_excluded_airlines(over, reason):
    c = contract_v3(max_stops=1, time_windows=[{"leg": 1, "dep_after": "06:00"}], airlines={"prefer": [], "exclude": ["FR"]})
    r = row_v3(legs=[leg_entry(1, **over), leg_entry(2)])
    assert ffr_rows.row_status(r, c, set(), [])[0] == "rejected" and reason in ffr_rows.row_status(r, c, set(), [])[1]

def test_cap_applies_per_leg_part():  # part 1 + part 2 of leg 1 each under the cap pass; one over -> rejected

def test_via_airport_without_ground_row_is_a_lead():
    c = contract_v3(); c["legs"][0]["from"] = group("ZRH", {"code": "BSL", "via": "rail"})
    r = row_v3(origin="BSL", legs=[leg_entry(1, **{"from": "BSL"}), leg_entry(2, to="BSL")])
    assert "ground unpriced (BSL)" in ffr_rows.row_status(r, c, set(), [])[1]
    assert ffr_rows.row_status(r, c, set(), [ground(), ground(date="2027-02-17", **{"from": "BSL", "to": "ZRH"})])[0] == "qualified"

def test_ground_row_the_day_before_needs_overnight_ok():  # ground dated 2027-02-02: lead unless overnight_ok on that airport; then also flagged (Task 5)

def test_ground_row_validation():  # missing price -> error; quote_state list -> ok but not counted (lead "ground unpriced (BSL)")

def test_phase_defaults_to_exact_and_discover_rows_keep_cell_ids():
    c = ffr_contract.normalize_contract(contract_v3(speed="fast"))
    assert ffr_rows.row_cell_id(row_v3(phase="discover"), c) == "economy/discover/ZZZ"
    assert ffr_rows.row_cell_id(row_v3(), c) == "economy/confirm/ZZZ"
    assert ffr_rows.row_cell_id(row_v3(), ffr_contract.normalize_contract(contract_v3())) == "economy/baseline/ZRH-ZZZ/2027-02-03_2027-02-17"
```

Also port the 2.x tests that still apply (baggage states, cabin bags, fx, per-person with infants, mixed cabin label, supersedes) from `tests/test_run_log_rows.py` into this file with the v3 builders, then delete `tests/test_run_log_rows.py`.

- [ ] **Step 2: Run to verify they fail** — `pytest tests/test_rows_v3.py -q` → FAIL.

- [ ] **Step 3: Implement `ffr_rows.py`** (validation, `row_cell_id`, gates, lead reasons, `ground_for`: cheapest `completed` ground record matching `{from,to}` in either order and `date` equal to the leg's date, or the day before when that airport's `overnight_ok` is true).

- [ ] **Step 4: Run to verify they pass** — PASS.

- [ ] **Step 5: Commit** — `git commit -m "feat(rows): leg-based rows, ground rows, v3 gates"`

---

### Task 5: Totals, ranking, cell states and check

**Files:**
- Modify: `skill/scripts/ffr_rows.py`
- Test: `tests/test_rank_v3.py`, `tests/test_check_v3.py`

**Interfaces:**
- Produces:
  - `all_in(row, contract, grounds) -> float`, `lower_bound(row, contract, grounds) -> float`
  - `risk_flags(row, contract, grounds) -> list[str]` (2.x flags plus `over budget`, `preferred airline`, `ground: rail ZRH-BSL`, `overnight before departure`)
  - `evaluate(contract, records) -> list[dict]`, `rank(contract, records, cabin=None) -> dict`, `cell_states(contract, records) -> list[dict]`, `check(contract, records) -> dict`, `pick_confirm_tuples(contract, records, top=3) -> dict[str, list[list[str]]]`
  - `records` may contain `type` `row`, `ground`, `resolve`.

- [ ] **Step 1: Write the failing tests**

```python
def test_all_in_adds_ground_rows_both_ways():  # tickets 400 + ground 32.4 + 32.4 -> 464.8

def test_rank_tie_breaks_prefer_airline_then_duration():  # equal totals: preferred LX first; flag "preferred airline"

def test_over_budget_is_flagged_not_hidden():  # budget 300, total 400 -> in qualified with flag "over budget"

def test_lower_bound_counts_missing_ground_as_zero_and_prunes():  # ported from 2.x pruning tests

def test_confirm_cell_closes_only_on_exact_rows_for_its_tuples():
    c = ffr_contract.normalize_contract(contract_v3(speed="fast"))
    c = ffr_contract.fill_confirm_cells(c, {"economy/ZZZ": [["2027-02-03", "2027-02-17"]]})
    states = {s["id"]: s for s in ffr_rows.cell_states(c, records(row_v3(phase="discover")))}
    assert states["economy/discover/ZZZ"]["state"] == "done"
    assert states["economy/confirm/ZZZ"]["state"] == "open" and "2027-02-03_2027-02-17" in states["economy/confirm/ZZZ"]["why"]
    states = {s["id"]: s for s in ffr_rows.cell_states(c, records(row_v3(phase="discover"), row_v3()))}
    assert states["economy/confirm/ZZZ"]["state"] == "done"

def test_confirm_cell_without_tuples_is_open():  # why == "no confirm tuples yet: run run_log.py confirm"

def test_region_without_shortlist_keeps_check_incomplete():  # open item "economy/discover: region 'SE Asia' has no shortlist"

def test_pick_confirm_tuples_takes_cheapest_within_cap_per_destination():  # 3 discover rows, top 2 -> the two cheapest tuples; a row over the cap is skipped

def test_check_warnings_ported():  # one source family, leads may beat best, no fx — ported from tests/test_run_log_check.py
```

Port the remaining 2.x ranking and check tests from `tests/test_run_log_rank.py`, `tests/test_run_log_check.py`, `tests/test_run_log_hardening.py`, `tests/test_run_log_v21.py` with v3 builders, then delete those files.

- [ ] **Step 2: Run to verify they fail** — FAIL.

- [ ] **Step 3: Implement** in `ffr_rows.py`. `cell_states` rules: `baseline` as 2.x; `discover` done when a populated `discover`-phase row exists for that destination; `confirm` open with `no confirm tuples yet` when `tuples` is empty, else open naming each tuple lacking a populated `exact` row; `crosscheck` counts families over both phases; `reprice` as 2.x; `check` adds an open item per empty region group.

- [ ] **Step 4: Run to verify they pass** — PASS.

- [ ] **Step 5: Commit** — `git commit -m "feat(rows): ranking with ground rows, fast-mode cell states, confirm picks"`

---

### Task 6: `run_log.py` CLI on the new modules

**Files:**
- Modify: `skill/scripts/run_log.py` (becomes storage + CLI; imports `ffr_contract`, `ffr_rows`; re-exports `UsageError`, `locked`, `load_run`, `resolve_run_dir`, `add_rows`, `runs_root`)
- Test: `tests/test_run_log_cli_v3.py`
- Delete: `tests/test_run_log_contract.py`, `tests/test_run_log_check.py` (ported in Tasks 4–5)

**Interfaces:**
- Produces commands: `init --contract FILE [--runs-root DIR]` (prints run dir, tuple count, cell count, region groups awaiting a shortlist); `shortlist --run DIR CODE[,CODE…]`; `confirm --run DIR [--top N]`; `add --run DIR --row FILE|-` (fare rows, attempts and ground rows in one array; `kind: "ground"` selects the ground validator; prints `gN completed ZRH-BSL 2027-02-03 32.40` for ground rows); `resolve`, `coverage`, `rank`, `check` as 2.x; `jobs --run DIR [--sessions N] [--top N] [--json]`.
- `plan_jobs(contract, records, sessions_per_site=2, top=3) -> list[dict]` in `run_log.py`: each job `{"session": "ffr-<source>-<n>", "source", "family", "engine_hint", "command": "<command line>", "cells": [ids]}`. Rules: one FlightList sweep job per open `discover` cell (`flightlist.py sweep --session … --run … --cabin C --from A+B --to DEST`); one Google sweep job per cabin for open `confirm` cells (`gflights.py sweep --session … --run … --cabins C --tuples …`); thorough baseline cells split across Google jobs by `sessions_per_site` (Google always 1); open `reprice` cells → a `kiwi.py fare` job per lead with a Kiwi booking URL, else a recipe reference (`references/airline-direct.md`); open hack cells → recipe reference `references/route-hacks.md`.
- `add_rows` writes `contract.json` back only via `shortlist`/`confirm` (which rewrite the file under the lock and append a `{"type": "contract", "at": …}` record).

- [ ] **Step 1: Write the failing CLI tests** (through `cli()`; set `FFR_RUNS` to `tmp_path`)

```python
def test_init_reports_tuples_and_region(tmp_path): # fast + region -> stdout has "1 region group awaiting shortlist"
def test_shortlist_then_coverage_shows_discover_cells(tmp_path):
def test_add_accepts_fare_ground_and_attempt_rows_in_one_array(tmp_path): # stdout lines "r1 lead: …", "g1 completed ZRH-BSL …", "r2 attempt"
def test_add_refuses_whole_batch_when_one_row_is_invalid(tmp_path):
def test_confirm_fills_tuples_from_discover_rows(tmp_path): # then coverage shows confirm cell open naming the tuple
def test_check_exit_codes(tmp_path): # 4 while open, 0 when complete (thorough, one tuple, qualified row + second family)
def test_jobs_plans_one_flightlist_sweep_per_discover_cell_and_one_google_job(tmp_path):
def test_run_lock_and_truncated_tail_ported(tmp_path): # from test_run_log_hardening.py
```

- [ ] **Step 2: Run to verify they fail** — FAIL.

- [ ] **Step 3: Rewrite `run_log.py`**: keep `runs_root`, `resolve_run_dir`, `_find_run_dir`, `load_run`, `_trim_partial_tail`, `locked`, `append_record`, `_read_json`, `_read_rows`, `main` from 2.x; replace the logic imports; add `cmd_shortlist`, `cmd_confirm`, `cmd_jobs`, `plan_jobs`; `cmd_rank` prints legs per row (`leg 1 2027-02-03 06:50 -> 18:40 15:50 1 stop KL`) and ground lines.

- [ ] **Step 4: Run the whole suite** — `pytest tests/ -q` → PASS (old `test_run_log_*` files deleted or ported). `python3 skill/scripts/run_log.py --help` exits 0.

- [ ] **Step 5: Commit** — `git commit -m "feat(run_log): v3 CLI with shortlist, confirm, ground rows and jobs"`

---

### Task 7: `browseract.py` — status, engine, session driver, challenge policy

**Files:**
- Create: `skill/scripts/browseract.py`
- Create: `tests/fake_browser_act.py` (installed as `browser-act` on a temporary `PATH`; behaviour chosen by `FAKE_BA_SCENARIO` env var: `missing`, `nokey`, `key`, `challenge`, `solved`)
- Test: `tests/test_browseract.py`

**Interfaces:**
- Produces:
  - `status(*, fresh=False, runner=run_cli, env=os.environ, state_dir=None, now=None) -> dict` with keys `installed, version, api_key ("env"|"config"|None), logged_in, stealth_quota, chrome_running, engine, checked_at`; cache file `<state>/browseract-status.json`, valid 24 h.
  - `ENGINES = ("browser-act-stealth", "browser-act", "browser-act-chrome", "claude-in-chrome", "builtin-browser", "cowork", "headless")`; `choose_engine(status: dict, host_tools: list[str]) -> str`.
  - `run_cli(args: list[str], *, timeout=120, input=None) -> subprocess.CompletedProcess` (binary from `shutil.which("browser-act")` or `~/.local/bin/browser-act`; raises `UsageError` when absent).
  - `class Session(name: str, browser: str | None = None, *, runner=run_cli)`: `open(url, headed=False)`, `navigate(url)`, `read_markdown() -> str`, `eval(js) -> str`, `wait_for(pattern: str, *, timeout=45, poll=1.5, sleep=time.sleep) -> str | None` (returns the page text when the regex matches), `network_status(codes=("403", "429")) -> list[dict]`, `solve_captcha() -> bool`, `remote_assist(objective) -> str` (the URL), `close()`; `SESSION_PREFIX = "ffr-"`.
  - `CHALLENGE = re.compile(...)` (2.x pattern plus `press and hold`, `verify you are human`, `Just a moment`).
  - `is_challenge(text: str, network: list[dict]) -> bool`
  - `handle_challenge(session, *, logged_in: bool, user_reachable: bool, notify=print, wait_for_change=None, timeout=600) -> str` returning `solved`, `assisted`, `user`, or `blocked`.
  - `close_all_mine(runner=run_cli) -> list[str]`
  - CLI: `browseract.py status [--fresh] [--json]`, `browseract.py engine [--host-tools a,b]`, `browseract.py close --all-mine`.
  - `UsageError` imported from `ffr_contract`.

- [ ] **Step 1: Write the fake CLI and the failing tests**

`tests/fake_browser_act.py` answers: `--version` → `browser-act 1.4.3`; `auth poll` → `registered` in scenario `key`, else `not registered` exit 1; `browser list` → JSON with one `chrome` browser; `browser list --type stealth` → `API key required. Sign up: https://browseract.com/…` exit 2 in `nokey`; `--session S get markdown` → a page from a file named by `FAKE_BA_PAGE`; `solve-captcha` → `solved=True` in `solved`, `solved=False` otherwise; `remote-assist` → `https://assist.example/abc`; `network requests --status 403` → `[]`; `session list`/`session close` → ok.

```python
def test_status_cli_missing(tmp_path, monkeypatch):  # PATH without the fake -> installed False, engine "claude-in-chrome" when host tool listed, no exception
def test_status_no_key_reports_login_hint(tmp_path, fake_cli):  # scenario nokey -> api_key None, logged_in False, engine "browser-act"
def test_status_key_from_env(tmp_path, fake_cli, monkeypatch):  # BROWSERACT_API_KEY set -> api_key "env", logged_in True, engine "browser-act-stealth"
def test_status_cache_used_within_24h_and_ignored_after(tmp_path, fake_cli):  # second call makes no CLI calls; with now=+25h it does
def test_choose_engine_ladder():  # stealth > chrome > chrome-direct > claude-in-chrome > builtin > cowork > headless
def test_session_wait_for_polls_until_pattern(fake_cli):  # fake pages loading.md then results.md -> returns text after 2 polls
def test_handle_challenge_solve_once_then_remote_assist(fake_cli):  # scenario challenge, logged_in True, user_reachable True -> "assisted"; solve-captcha called exactly once (fake logs calls to a file)
def test_handle_challenge_without_key_and_user_is_blocked(fake_cli):  # -> "blocked"; no solve-captcha call
def test_handle_challenge_user_watching_own_browser(fake_cli):  # logged_in False, user_reachable True, engine chrome-direct -> "user"
def test_close_all_mine_only_closes_ffr_sessions(fake_cli):
def test_cli_status_json(fake_cli):  # subprocess run of browseract.py status --json parses
```

- [ ] **Step 2: Run to verify they fail** — FAIL.

- [ ] **Step 3: Implement `browseract.py`**. Detection order in `status`: `--version`; env key; config `api_key` (path from `BROWSERACT_CONFIG` env, else `~/.config/browser-act/config.json`, else `~/.browser-act/config.json`, best effort); `auth poll` exit 0 and stdout containing `registered`; finally `browser list --type stealth` refusal text containing `API key`. `chrome_running` from `browser list` naming a `chrome-direct` browser. `handle_challenge` order per spec section 7.

- [ ] **Step 4: Run to verify they pass** — PASS; `python3 skill/scripts/browseract.py --help` exits 0.

- [ ] **Step 5: Commit** — `git commit -m "feat(browseract): status, engine ladder, session driver, challenge policy"`

---

### Task 8: `gflights.py` on the driver — tuples, N legs, explore

**Files:**
- Modify: `skill/scripts/gflights.py`
- Test: `tests/test_gflights.py` (update), new fixture `tests/fixtures/gflights/explore.md` if captured

**Interfaces:**
- Produces: `legs_for_tuple(contract: dict, tuple: list[str], origin: str | None = None, destination: str | None = None) -> list[str]` (leg strings `FROM-TO@DATE`; for a return trip origin/destination override both legs; for multi-city each leg's home airport unless overridden); `sweep(run_dir, session, *, cabins, tuples, origin, destination, top, pause, …)` recording rows with `legs` (one entry, `leg: 1`, `part: 1`), `dates` = the tuple, `phase: "exact"`; on a challenge, `handle_challenge` is called and the row notes the outcome; `explore_url(region: str, origin: str, window: tuple[str, str], cabin: str, currency: str) -> str`; `parse(text, anchor, explore=False)` returning `{"state", "destinations": [{"city", "airport", "price", "currency", "dates"}]}` in explore mode; CLI `sweep --tuples`, `explore --region … --from ZRH --window 2027-02-01,2027-02-10`, `parse --explore`.

- [ ] **Step 1: Try to capture an Explore fixture** with the container's Chromium (`PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers`): open the explore URL, wait 15 s, save `main` innerText trimmed to the destination list as `tests/fixtures/gflights/explore.md`. If the page is a challenge or empty, record that in the commit message and skip the explore parser tests (steps marked *explore* below); `parse --explore` then returns `{"state": "unavailable"}` and `discovery.md` says to read cards by hand.

- [ ] **Step 2: Update the failing tests**: existing URL tests unchanged; sweep tests build a v3 run (`contract_v3`) and a fake `Session` object with `open/navigate/read_markdown/wait_for`; assert rows carry `legs[0]["leg"] == 1`, `dates == tuple`, `phase == "exact"`; `test_legs_for_tuple_return_and_multicity`; *explore*: `test_parse_explore_lists_destinations_with_prices`.

- [ ] **Step 3: Run to verify they fail** — FAIL.

- [ ] **Step 4: Implement**: replace `BrowserActPage` with `browseract.Session`; `_card_row` emits `legs`/`dates`; `_mismatch` checks the tuple's first date; `explore_url` uses the Explore page (`https://www.google.com/travel/explore?tfs=…` built with the same protobuf builder: destination field left empty, `region` as a free-text destination field 14 `_field(2, region)` without the airport wrapper) — if the live capture shows the URL needs another shape, use the captured URL and note it in `google-flights-browser.md`.

- [ ] **Step 5: Run to verify they pass** — PASS.

- [ ] **Step 6: Commit** — `git commit -m "feat(gflights): tuples, N-leg sweeps on the shared driver, explore"`

---

### Task 9: `flightlist.py` — v3 rows and a form-driving sweep

**Files:**
- Modify: `skill/scripts/flightlist.py`
- Test: `tests/test_flightlist.py` (update)

**Interfaces:**
- Produces: `rows_for(contract, raw_cards, *, top=1, cabin=None, hack=None, engine="browser", phase="discover", retrieved_at=None) -> tuple[list[dict], list[str]]` grouping cards by date tuple, emitting `legs` with `leg` 1 and 2 and `dates`; `sweep(run_dir, session, *, cabin, origins: list[str], destination: str, top=1, limit=200, log=…) -> dict` driving the form through `session.eval` with the recipe's snippets (airport typing via `session.runner` `input` with real keys, both range pickers set from the contract's leg-1 range and leg-2 window, `#type/#class/#currency/#checkedbags/#sort/#stops/#connections` set, submit, `wait_for(r"li\.flight|No flights")`, extraction snippet), recording rows and printing uncovered tuples; CLI `sweep --session S --run DIR --cabin C --from ZRH+BSL+GVA --to BKK [--top N]`.
- Parser tolerance: `SUMMARY`/`SEGMENT` accept `Direct|Nonstop`, 12-hour and 24-hour clocks, `,`/`'` thousands separators.

- [ ] **Step 1: Update the failing tests**: `test_rows_group_cards_by_tuple_and_emit_legs` on `range_cards.json` with a v3 contract whose window covers the fixture dates; `test_rows_report_uncovered_tuples`; `test_sweep_drives_form_and_records_rows` with a fake session whose `eval` returns the fixture JSON and whose calls are recorded (assert the order: airports, pickers, settings, submit, extract); `test_parse_accepts_24h_and_nonstop` on a synthetic card string.

- [ ] **Step 2: Run to verify they fail** — FAIL.

- [ ] **Step 3: Implement** — PASS after `pytest tests/test_flightlist.py -q`.

- [ ] **Step 4: Commit** — `git commit -m "feat(flightlist): v3 rows and an unattended range-search sweep"`

---

### Task 10: `kiwi.py` — fare-selection page to a completed row

**Files:**
- Create: `skill/scripts/kiwi.py`
- Create: `tests/fixtures/kiwi/fare_selection.md` (captured if possible; otherwise a synthetic page marked `<!-- synthetic: modelled on the 2026-10-09 KLM families -->` with families `Light`, `Standard`, `Flex`, prices `CHF 1,555.26 / 1,923.08 / 2,131.25`, bag lines `No checked bag`, `1 × 23 kg checked bag`, `1 × 23 kg checked bag`)
- Test: `tests/test_kiwi.py`

**Interfaces:**
- Produces: `parse_fares(text: str) -> list[dict]` (`{"family", "price", "currency", "checked_bag": bool, "cabin_bag": bool}`); `pick_family(fares, checked_per_person: int) -> dict | None` (cheapest with a checked bag when bags are requested, else cheapest); `completed_row(list_row: dict, fare: dict, url: str, engine: str) -> dict` (copies legs, dates, cabin, airports; `tickets[0]` becomes `completed`, provider `Kiwi.com`, `baggage` `included`/`fee_required`, `supersedes` the list row id); CLI `kiwi.py fare --session S --run DIR --supersedes rN URL [--engine E]` which opens the URL, waits for a family price, parses, and `add`s the row.

- [ ] **Step 1: Write the failing tests**: `test_parse_fares_reads_families_prices_and_bags`, `test_pick_family_cheapest_with_bag`, `test_completed_row_supersedes_and_keeps_legs`, `test_cli_fare_adds_completed_row` (fake session returns the fixture; `rank` then shows the row qualified).

- [ ] **Step 2: Run to verify they fail** — FAIL.

- [ ] **Step 3: Implement `kiwi.py`** — PASS.

- [ ] **Step 4: Commit** — `git commit -m "feat(kiwi): fare-selection parser and completed rows"`

---

### Task 11: `source_ledger.py` — new ladder, pacing, Asia candidates

**Files:**
- Modify: `skill/scripts/source_ledger.py`
- Test: `tests/test_source_ledger.py` (update)

**Interfaces:**
- Produces: `ENGINE_RUNG = {"browser-act-stealth": 1, "browser-act": 2, "browser-act-chrome": 3, "claude-in-chrome": 3, "builtin-browser": 3, "cowork": 3}`, `headless*` → 4; registry rows for `qatar-direct` (exists), `emirates-direct`, `turkish-direct` (exists), `singapore-direct`, `thai-direct`, `airasia-direct`, `scoot-direct`, `trip-com` (exists), `google-explore` (role `discovery`, family `google`); per-source `pace_seconds` (Google 12, default 8) and `sessions_per_site` (Google 1, default 2) in the registry and in `order --json` output; `order` text prints `pace=12s sessions=1` per USE row.

- [ ] **Step 1: Update tests**: `test_order_marks_lower_rung_failures_as_reprobe` with the new rungs (a block on `browser-act-stealth` with `--engine claude-in-chrome` → RE-PROBE); `test_registry_has_asia_candidates_untested`; `test_order_json_carries_pace_and_sessions`.
- [ ] **Step 2: Run to verify they fail** — FAIL.
- [ ] **Step 3: Implement** — PASS.
- [ ] **Step 4: Commit** — `git commit -m "feat(ledger): BrowserAct-first rungs, pacing, Asia candidates"`

---

### Task 12: References rewritten for v3

**Files:**
- Rewrite: `skill/references/intake.md`, `skill/references/browser-engines.md`
- Create: `skill/references/discovery.md`
- Modify: `skill/references/qualification.md`, `route-hacks.md`, `source-ladder.md`, `source-health.md`, `google-flights-browser.md`, `flightlist-browser.md`, `airline-direct.md` (engine names), `edreams-browser.md`, `ita-matrix-browser.md` (engine names only), `historical-observations.md` (append anything the Task 8 capture found)
- Test: `tests/test_internal_links.py` (existing), new `tests/test_references_v3.py`

**Interfaces:**
- `intake.md`: the 18-line questionnaire from spec section 5 as a quoted template, the field table (contract keys per line), the spec's example contract verbatim, and the `init`/`shortlist`/`confirm` commands.
- `browser-engines.md`: ladder table from spec section 7, `browseract.py status` JSON and the two intake lines (logged in / not logged in) as exact copy, browsers and sessions, parallelism and pacing, challenge policy steps 1–5, the engine mapping table from 2.x, `close --all-mine`.
- `discovery.md`: the three sources, the shortlist message template (teaser prices labelled leads), `run_log.py shortlist`, a candidate-gateway table for Southeast Asia (BKK, DMK, SIN, KUL, SGN, HAN, MNL, CGK, DPS, RGN, PNH) and for South-East-Asia-adjacent hubs used for positioning (DOH, DXB, IST, AUH) marked "candidates only, never prices".
- `qualification.md`: legs instead of directions, the v3 row example from a real Kiwi-qualified KLM row shape, ground rows, `kiwi.py fare`, lead-reason table with `leg N not selected` and `ground unpriced (XXX)`.
- `route-hacks.md`: three hacks, multi-city native, open-jaw/stopover leg parts.

- [ ] **Step 1: Write `tests/test_references_v3.py`**: `intake.md` contains all 18 numbered items and the strings `speed`, `shortlist`, `after_leg`; `browser-engines.md` contains `browser-act-stealth`, `auth login`, `auth poll`, `solve-captcha`, `remote-assist`, `close --all-mine`; `discovery.md` contains `run_log.py shortlist`; no reference mentions `nearby_origin`, `alt_destination`, `directions` or `outbound_date` (grep the whole `skill/` tree).
- [ ] **Step 2: Run** — FAIL.
- [ ] **Step 3: Write the references** (follow `mattpocock-skills:writing-for-agents` conventions already used: short imperative sections, exact commands, dated evidence kept dated).
- [ ] **Step 4: Run** `pytest tests/test_references_v3.py tests/test_internal_links.py -q && python3 scripts/validate.py --strict` — PASS.
- [ ] **Step 5: Commit** — `git commit -m "docs(references): v3 intake, engines, discovery, qualification, hacks"`

---

### Task 13: SKILL.md 3.0.0, safety doc, scenarios, changelog, README

**Files:**
- Rewrite: `skill/SKILL.md` (version `3.0.0`), `docs/safety-and-provenance.md` (browser section per spec section 11)
- Modify: `integrations/claude-code/.claude-plugin/plugin.json` (version, description), `CHANGELOG.md` (`## [3.0.0]`), `README.md` (how it works, ladder, install), `integrations/codex/AGENTS.md`, `integrations/cowork/README.md`, `tests/scenarios/04-unattended-captcha.md` (rewritten criteria), new `tests/scenarios/07-multicity-region.md`, `08-full-questionnaire-just-go.md`, `09-no-browseract-login.md`
- Test: `tests/test_acceptance_validation.py` (version agreement, word budget), `tests/test_references_v3.py` (extend: SKILL.md names `browseract.py status`, `discovery.md`, `jobs`, the six phases)

**Interfaces:**
- SKILL.md phases: 0 Browser check (`browseract.py status`, account line), 1 Intake (questionnaire pointer), 2 Discovery (regions), 3 Collect (`jobs`, sweeps, parallel sessions), 4 Hacks, 5 Qualify (legs, ground rows, `kiwi.py`), 6 Cross-check and report; key rule and temptation table kept; final checklist updated.
- Scenario 04 pass criteria per spec section 11; 07 prompt: "Zurich area to somewhere in Southeast Asia, 12–16 nights in February, 2 adults, economy and premium, 1 bag each, CHF, max 20 h, multi-city fine if it is cheaper" with observations of a `status` result (logged in) and an `init`; 08 prompt: "cheap flights to Lisbon next month, don't ask questions" expecting all 18 defaults listed; 09 observations: `status` says not installed/no key, expecting the install ask and the two auth commands, and no stall.

- [ ] **Step 1: Extend `tests/test_references_v3.py`** with the SKILL.md assertions and the scenario file names; run → FAIL.
- [ ] **Step 2: Write SKILL.md, safety doc, scenarios, changelog, README, plugin.json.**
- [ ] **Step 3: Run** `python3 scripts/validate.py --strict && pytest tests/ -q` → PASS, word count printed by `python3 -c` under 2,000.
- [ ] **Step 4: Commit** — `git commit -m "docs(skill): 3.0.0 SKILL.md, safety policy, scenarios, changelog"`

---

### Task 14: Pressure scenarios, final verification, push

**Files:**
- Modify: `tests/scenarios/0{4,5,6,7,8,9}-*.md` (record results), `skill/references/historical-observations.md` if a scenario surfaces a recipe gap, `docs/manual-release-checklist.md`

- [ ] **Step 1: Run scenarios 04–09 with fresh general-purpose subagents** per `tests/scenarios/README.md`, each with its own `FFR_RUNS`/`FFR_LEDGER` under the scratchpad and the fake `browser-act` on `PATH` where the scenario needs it. Score every criterion; fix wording gaps in SKILL.md or references and re-run the failed scenario once.
- [ ] **Step 2: Record results** under an `## After (v3.0.0)` heading in each scenario file.
- [ ] **Step 3: Full verification**

Run: `python3 scripts/package.py && python3 scripts/validate.py --strict && .venv/bin/python -m pytest tests/ -q && git status --porcelain`
Expected: validator OK, all tests pass, working tree clean except intended changes.

- [ ] **Step 4: Commit and push**

```bash
git add -A && git commit -m "test(scenarios): v3.0.0 results" && git push -u origin ccr-1d6f6aef-bds78x
```
