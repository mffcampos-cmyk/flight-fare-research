#!/usr/bin/env python3
"""Run evidence log for the flight-fare-research skill (stdlib only, no network).

The agent performs every search; this script only keeps one run's books: the
search contract, the expected comparisons, every observation row, the computed
lead/qualified status of each row, and whether the run is complete.

  run_log.py init --contract FILE [--runs-root DIR]
  run_log.py add --row FILE|- [--run DIR]
  run_log.py resolve CELL --as na|no_fare|none_qualify --reason TEXT [--run DIR]
  run_log.py coverage [--run DIR] [--json]
  run_log.py rank [--run DIR] [--cabin C] [--json]
  run_log.py check [--run DIR] [--json]     exit 0 complete, 4 incomplete

Exit 2 means a usage or validation error. Runs live in $FFR_RUNS, else
$XDG_STATE_HOME/flight-fare-research/runs, else
~/.local/state/flight-fare-research/runs; --run defaults to the most recently
modified run directory there.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import re
import sys
from datetime import date, timedelta

HACKS = ("split", "open_jaw", "nearby_origin", "alt_destination", "stopover")
CABINS = ("economy", "premium", "business", "first")
SCOPES = ("quick", "full")
TRIP_TYPES = ("return", "one_way")
EXIT_OK, EXIT_USAGE, EXIT_INCOMPLETE = 0, 2, 4

DEFAULT_FULL_HACKS = [h for h in HACKS if h != "stopover"]
RUN_ID = re.compile(r"^[a-z0-9][a-z0-9-]*$")
HHMMSS = re.compile(r"^\d\d:\d\d:\d\d$")


class UsageError(Exception):
    """A user-facing error that maps to exit code 2."""


def duration_to_seconds(hhmmss: str) -> int:
    """Convert a strict two-digit ``HH:MM:SS`` duration to seconds."""
    if not isinstance(hhmmss, str) or not HHMMSS.match(hhmmss) or not hhmmss.isascii():
        raise ValueError("duration must use HH:MM:SS format")
    hours, minutes, seconds = (int(p) for p in hhmmss.split(":"))
    if minutes >= 60 or seconds >= 60:
        raise ValueError("minutes and seconds must be between 00 and 59")
    return hours * 3600 + minutes * 60 + seconds


def runs_root() -> str:
    if os.environ.get("FFR_RUNS"):
        return os.environ["FFR_RUNS"]
    state = os.environ.get("XDG_STATE_HOME") or os.path.join(os.path.expanduser("~"), ".local", "state")
    return os.path.join(state, "flight-fare-research", "runs")


# --------------------------------------------------------------------------- contract

def _is_date(value) -> bool:
    try:
        date.fromisoformat(value)
        return True
    except (TypeError, ValueError):
        return False


def _date_errors(dates, trip_type) -> list[str]:
    if not isinstance(dates, dict):
        return ["dates must be an object"]
    kinds = [k for k in ("pairs", "rolling", "cartesian", "outbound") if k in dates]
    if len(kinds) != 1:
        return ["dates needs exactly one of pairs, rolling, cartesian, outbound"]
    kind = kinds[0]
    spec = dates[kind]
    if trip_type == "one_way":
        if kind != "outbound":
            return ["dates: one-way trips use dates.outbound (a list of dates)"]
    elif kind == "outbound":
        return ["dates.outbound is for one-way trips; use pairs, rolling or cartesian"]
    if kind == "outbound":
        if not isinstance(spec, list) or not spec or not all(_is_date(d) for d in spec):
            return ["dates.outbound must be a non-empty list of YYYY-MM-DD dates"]
    elif kind == "pairs":
        ok = isinstance(spec, list) and spec and all(
            isinstance(p, list) and len(p) == 2 and all(_is_date(d) for d in p) and p[1] >= p[0]
            for p in spec)
        if not ok:
            return ["dates.pairs must be a non-empty list of [outbound, return] dates, return not before outbound"]
    elif kind == "rolling":
        if not isinstance(spec, dict):
            return ["dates.rolling must be an object"]
        errors = [f"dates.rolling.{k} must be a YYYY-MM-DD date"
                  for k in ("first_outbound", "last_outbound") if not _is_date(spec.get(k))]
        days = spec.get("trip_days")
        if not isinstance(days, int) or isinstance(days, bool) or days < 0:
            errors.append("dates.rolling.trip_days must be a non-negative integer")
        if not errors and spec["first_outbound"] > spec["last_outbound"]:
            errors.append("dates.rolling.first_outbound must not be after last_outbound")
        return errors
    elif kind == "cartesian":
        if not isinstance(spec, dict):
            return ["dates.cartesian must be an object"]
        errors = [f"dates.cartesian.{k} must be a YYYY-MM-DD date"
                  for k in ("outbound_from", "outbound_to", "return_from", "return_to")
                  if not _is_date(spec.get(k))]
        if spec.get("confirmed") is not True:
            errors.append("dates.cartesian needs \"confirmed\": true (the user accepted varying trip lengths)")
        return errors
    return []


def validate_contract(contract: dict) -> list[str]:
    """Return a list of problems with a search contract; [] when valid."""
    if not isinstance(contract, dict):
        return ["contract must be a JSON object"]
    errors = []
    run_id = contract.get("run_id")
    if not isinstance(run_id, str) or not RUN_ID.match(run_id):
        errors.append("run_id is required: lowercase letters, digits and hyphens")
    if contract.get("scope") not in SCOPES:
        errors.append("scope is required: quick or full")
    trip_type = contract.get("trip_type")
    if trip_type not in TRIP_TYPES:
        errors.append("trip_type is required: return or one_way")
    travelers = contract.get("travelers")
    adults = travelers.get("adults") if isinstance(travelers, dict) else None
    if not isinstance(adults, int) or isinstance(adults, bool) or adults < 1:
        errors.append("travelers.adults must be an integer >= 1")
    currency = contract.get("currency")
    if not isinstance(currency, str) or not re.match(r"^[A-Z]{3}$", currency):
        errors.append("currency is required: a three-letter code such as CHF")
    for key in ("origins", "destinations"):
        value = contract.get(key)
        if not isinstance(value, list) or not value or not all(isinstance(v, str) and v for v in value):
            errors.append(f"{key} must be a non-empty list of airport codes")
    if "dates" not in contract:
        errors.append("dates is required")
    else:
        errors.extend(_date_errors(contract["dates"], trip_type))
    cabins = contract.get("cabins")
    if not isinstance(cabins, list) or not cabins:
        errors.append("cabins must be a non-empty list")
    elif any(c not in CABINS for c in cabins):
        errors.append(f"cabins must be drawn from {', '.join(CABINS)}")
    bags = contract.get("bags")
    checked = bags.get("checked_per_person") if isinstance(bags, dict) else None
    if not isinstance(checked, int) or isinstance(checked, bool) or checked < 0:
        errors.append("bags.checked_per_person is required: an integer >= 0")
    hacks = contract.get("hacks")
    if hacks is not None and (not isinstance(hacks, list) or any(h not in HACKS for h in hacks)):
        errors.append(f"hacks must be drawn from {', '.join(HACKS)}")
    cap = contract.get("max_duration")
    if cap is not None:
        try:
            duration_to_seconds(cap.get("value") if isinstance(cap, dict) else None)
        except ValueError:
            errors.append("max_duration.value must be HH:MM:SS (or max_duration null for no cap)")
        if isinstance(cap, dict) and not isinstance(cap.get("strict"), bool):
            errors.append("max_duration.strict must be true or false")
    return errors


def normalize_contract(contract: dict) -> dict:
    """Return a copy of a valid contract with optional fields defaulted."""
    c = copy.deepcopy(contract)
    c.setdefault("nearby_origins", [])
    c.setdefault("alt_destinations", [])
    c.setdefault("max_duration", None)
    positioning = {"allowed": False, "rail_ok": False, "overnight_ok": False}
    positioning.update(c.get("positioning") or {})
    c["positioning"] = positioning
    c.setdefault("self_transfer_ok", False)
    if c["scope"] == "quick":
        c["hacks"] = ["nearby_origin"]
    elif c.get("hacks") is None:
        c["hacks"] = list(DEFAULT_FULL_HACKS)
    c["hacks"] = [h for h in HACKS if h in c["hacks"]]
    c.setdefault("event", None)
    c.setdefault("assumptions", [])
    c["travelers"].setdefault("children_ages", [])
    c["travelers"].setdefault("infants", 0)
    return c


def expand_dates(dates: dict, trip_type: str) -> list[list]:
    """Expand a contract's dates into sorted [outbound, return-or-None] pairs."""
    def iso_range(first, last):
        day, end = date.fromisoformat(first), date.fromisoformat(last)
        while day <= end:
            yield day
            day += timedelta(days=1)

    if trip_type == "one_way" or "outbound" in dates:
        pairs = [[d, None] for d in dates["outbound"]]
    elif "pairs" in dates:
        pairs = [list(p) for p in dates["pairs"]]
    elif "rolling" in dates:
        r = dates["rolling"]
        pairs = [[d.isoformat(), (d + timedelta(days=r["trip_days"])).isoformat()]
                 for d in iso_range(r["first_outbound"], r["last_outbound"])]
    else:
        c = dates["cartesian"]
        pairs = [[o.isoformat(), r.isoformat()]
                 for o in iso_range(c["outbound_from"], c["outbound_to"])
                 for r in iso_range(c["return_from"], c["return_to"]) if r >= o]
    unique = {tuple(p) for p in pairs}
    return sorted((list(p) for p in unique), key=lambda p: (p[0], p[1] or ""))


def baseline_cell_id(cabin: str, origin: str, destination: str, outbound: str, ret: str | None) -> str:
    dates = outbound if ret is None else f"{outbound}_{ret}"
    return f"{cabin}/baseline/{origin}-{destination}/{dates}"


def _hack_auto(contract: dict, hack: str):
    def na(reason):
        return {"as": "na", "reason": reason}

    if hack in ("split", "open_jaw") and contract["trip_type"] == "one_way":
        return na("one-way trip")
    if hack == "nearby_origin":
        if not contract["positioning"]["allowed"]:
            return na("positioning not allowed")
        if not contract["nearby_origins"]:
            return na("no nearby origins given")
    if hack == "alt_destination" and not contract["alt_destinations"]:
        return na("no alternative destinations")
    return None


def build_cells(contract: dict) -> list[dict]:
    """List the comparisons a run must finish, in report order."""
    c = normalize_contract(contract)
    pairs = expand_dates(c["dates"], c["trip_type"])
    cells = []
    for cabin in c["cabins"]:
        for origin in c["origins"]:
            for dest in c["destinations"]:
                for out, ret in pairs:
                    cells.append({"id": baseline_cell_id(cabin, origin, dest, out, ret), "kind": "baseline",
                                  "cabin": cabin, "origin": origin, "destination": dest,
                                  "outbound_date": out, "return_date": ret, "auto": None})
        for hack in c["hacks"]:
            cells.append({"id": f"{cabin}/hack/{hack}", "kind": "hack", "cabin": cabin,
                          "hack": hack, "auto": _hack_auto(c, hack)})
        cells.append({"id": f"{cabin}/crosscheck", "kind": "crosscheck", "cabin": cabin, "auto": None})
        cells.append({"id": f"{cabin}/reprice", "kind": "reprice", "cabin": cabin, "auto": None})
    return cells


# --------------------------------------------------------------------------- commands

def _read_json(path: str):
    try:
        if path == "-":
            return json.load(sys.stdin)
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError) as exc:
        raise UsageError(f"cannot read JSON from {path}: {exc}")


def cmd_init(args) -> int:
    contract = _read_json(args.contract)
    errors = validate_contract(contract)
    if errors:
        raise UsageError("invalid contract:\n" + "\n".join(f"  - {e}" for e in errors))
    c = normalize_contract(contract)
    c["date_pairs"] = expand_dates(c["dates"], c["trip_type"])
    c["cells"] = build_cells(c)
    run_dir = os.path.join(args.runs_root or runs_root(), c["run_id"])
    if os.path.exists(run_dir):
        raise UsageError(f"run directory already exists: {run_dir} (choose another run_id)")
    os.makedirs(run_dir)
    with open(os.path.join(run_dir, "contract.json"), "w", encoding="utf-8") as handle:
        json.dump(c, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    open(os.path.join(run_dir, "rows.jsonl"), "w", encoding="utf-8").close()
    auto = sum(1 for cell in c["cells"] if cell["auto"])
    print(run_dir)
    print(f"{len(c['date_pairs'])} date pair(s), {len(c['cells'])} comparison cell(s), {auto} not applicable")
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("init", help="validate a contract and create a run")
    p.add_argument("--contract", required=True, help="contract JSON file, or - for stdin")
    p.add_argument("--runs-root", help="directory holding runs (default: see module docstring)")
    p.set_defaults(func=cmd_init)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except UsageError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_USAGE


if __name__ == "__main__":
    sys.exit(main())
