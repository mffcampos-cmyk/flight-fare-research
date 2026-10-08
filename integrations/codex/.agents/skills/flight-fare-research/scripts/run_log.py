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
from datetime import date, datetime, timedelta

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


# --------------------------------------------------------------------------- rows

OUTCOMES = ("populated", "blocked", "empty", "error")
QUOTE_STATES = ("list", "completed", "repriced")
BAGGAGE = ("included", "fee_required", "unverified")
PRICE_BASES = ("total", "per_person")
ATTEMPT_FIELDS = ("source", "family", "engine", "outcome", "url", "retrieved_at", "cabin")
POPULATED_FIELDS = ("currency", "origin", "destination", "outbound_date", "tickets", "directions")


def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value == value


def validate_row(row: dict, contract: dict) -> list[str]:
    """Return a list of problems with an observation row; [] when valid."""
    if not isinstance(row, dict):
        return ["row must be a JSON object"]
    errors = [f"{field} is required" for field in ATTEMPT_FIELDS if row.get(field) in (None, "")]
    if row.get("outcome") not in (None, "") and row["outcome"] not in OUTCOMES:
        errors.append(f"outcome must be one of {', '.join(OUTCOMES)}")
    stamp = row.get("retrieved_at")
    if stamp not in (None, ""):
        try:
            if datetime.fromisoformat(str(stamp)).tzinfo is None:
                errors.append("retrieved_at needs a timezone offset, e.g. 2026-10-08T14:03:00+02:00")
        except ValueError:
            errors.append("retrieved_at must be an ISO 8601 timestamp with a timezone offset")
    hack = row.get("hack")
    if hack is not None and hack not in HACKS:
        errors.append(f"hack must be null or one of {', '.join(HACKS)}")
    if row.get("price_basis", "total") not in PRICE_BASES:
        errors.append(f"price_basis must be one of {', '.join(PRICE_BASES)}")
    if row.get("outcome") != "populated":
        return errors
    errors.extend(f"{field} is required for a populated row" for field in POPULATED_FIELDS
                  if field not in row or row[field] in (None, ""))
    tickets = row.get("tickets")
    if "tickets" in row and (not isinstance(tickets, list) or not tickets):
        errors.append("tickets must be a non-empty list")
    for n, t in enumerate(tickets if isinstance(tickets, list) else [], 1):
        if not isinstance(t, dict):
            errors.append(f"tickets[{n}] must be an object")
            continue
        if not _is_number(t.get("price")) or t["price"] < 0:
            errors.append(f"tickets[{n}].price must be a non-negative number (no currency text)")
        if t.get("quote_state") not in QUOTE_STATES:
            errors.append(f"tickets[{n}].quote_state must be one of {', '.join(QUOTE_STATES)}")
        if t.get("baggage") not in BAGGAGE:
            errors.append(f"tickets[{n}].baggage must be one of {', '.join(BAGGAGE)}")
        if t.get("bag_fee") is not None and (not _is_number(t["bag_fee"]) or t["bag_fee"] < 0):
            errors.append(f"tickets[{n}].bag_fee must be null or a non-negative number")
    if "directions" in row and not isinstance(row["directions"], list):
        errors.append("directions must be a list")
    components = row.get("components") or {}
    if not isinstance(components, dict):
        errors.append("components must be an object")
    else:
        errors.extend(f"components.{k} must be null or a non-negative number" for k, v in components.items()
                      if v is not None and (not _is_number(v) or v < 0))
    fx = row.get("fx")
    if fx is not None and (not isinstance(fx, dict) or not _is_number(fx.get("rate")) or fx["rate"] <= 0):
        errors.append("fx must be null or {\"rate\": number > 0, \"date\": ..., \"source\": ...}")
    return errors


def row_cell_id(row: dict) -> str:
    if row.get("hack"):
        return f"{row.get('cabin')}/hack/{row['hack']}"
    return baseline_cell_id(row.get("cabin"), row.get("origin"), row.get("destination"),
                            row.get("outbound_date"), row.get("return_date"))


def _hard_gate_reasons(row: dict, c: dict) -> list[str]:
    reasons = []
    cap = c.get("max_duration")
    if cap:
        limit = duration_to_seconds(cap["value"])
        kind = "strict" if cap["strict"] else "inclusive"
        for d in row.get("directions") or []:
            try:
                seconds = duration_to_seconds(d.get("duration"))
            except ValueError:
                continue
            if seconds > limit or (cap["strict"] and seconds == limit):
                reasons.append(f"{d.get('dir')} duration {d['duration']} breaks {kind} cap {cap['value']}")
    if not c["self_transfer_ok"] and any(d.get("self_transfer") for d in row.get("directions") or []):
        reasons.append("self-transfer not allowed")
    if row.get("cabin") not in c["cabins"]:
        reasons.append("cabin not requested")
    pair = [row.get("outbound_date"), row.get("return_date") if c["trip_type"] == "return" else None]
    if pair not in expand_dates(c["dates"], c["trip_type"]):
        reasons.append("dates not in contract")
    hack = row.get("hack")
    origins = c["nearby_origins"] if hack == "nearby_origin" else c["origins"]
    if row.get("origin") not in origins:
        reasons.append("origin not in contract")
    if hack == "alt_destination":
        destinations = c["alt_destinations"]
    elif hack == "open_jaw":
        destinations = c["destinations"] + c["alt_destinations"]
    else:
        destinations = c["destinations"]
    if row.get("destination") not in destinations:
        reasons.append("destination not in contract")
    components = row.get("components") or {}
    if not c["positioning"]["allowed"] and (hack == "nearby_origin" or "positioning" in components):
        reasons.append("positioning not allowed")
    if row.get("positioning_overnight") and not c["positioning"]["overnight_ok"]:
        reasons.append("overnight positioning not allowed")
    return reasons


def _lead_reasons(row: dict, c: dict) -> list[str]:
    reasons = []
    dirs = row.get("directions") or []
    present = {d.get("dir") for d in dirs}
    if "out" not in present:
        reasons.append("outbound not selected")
    if c["trip_type"] == "return" and "ret" not in present:
        reasons.append("return not selected")
    for d in dirs:
        try:
            duration_to_seconds(d.get("duration"))
        except ValueError:
            reasons.append(f"duration unknown ({d.get('dir')})")
    tickets = row.get("tickets") or []
    if any(t.get("quote_state") == "list" for t in tickets):
        reasons.append("list fare not repriced")
    if c["bags"]["checked_per_person"] > 0:
        if any(t.get("baggage") == "unverified" for t in tickets):
            reasons.append("baggage unverified")
        if any(t.get("baggage") == "fee_required" and t.get("bag_fee") is None for t in tickets):
            reasons.append("bag fee unknown")
    reasons.extend(f"{name} unpriced" for name, value in (row.get("components") or {}).items() if value is None)
    if row.get("currency") != c["currency"] and not row.get("fx"):
        reasons.append("currency differs; no fx recorded")
    if row.get("price_basis") == "per_person" and c["travelers"].get("infants"):
        reasons.append("per-person price with infants; record the total")
    return reasons


def row_status(row: dict, contract: dict, superseded: set[str]) -> tuple[str, list[str]]:
    """Compute a row's status and the reasons behind it (never asserted by the agent)."""
    c = normalize_contract(contract)
    if row.get("id") in superseded:
        return "superseded", []
    if row.get("outcome") != "populated":
        return "attempt", []
    hard = _hard_gate_reasons(row, c)
    if hard:
        return "rejected", hard
    soft = _lead_reasons(row, c)
    if soft:
        return "lead", soft
    return "qualified", []


def _sum_parts(row: dict, c: dict) -> float:
    tickets = row.get("tickets") or []
    fares = sum(t.get("price") or 0 for t in tickets)
    if row.get("price_basis") == "per_person":
        fares *= c["travelers"]["adults"] + len(c["travelers"]["children_ages"])
    bags = 0.0
    if c["bags"]["checked_per_person"] > 0:
        bags = sum(t.get("bag_fee") or 0 for t in tickets if t.get("baggage") == "fee_required")
    extras = sum(v for v in (row.get("components") or {}).values() if v is not None)
    total = fares + bags + extras
    if row.get("fx"):
        total *= row["fx"]["rate"]
    return round(total, 2)


def all_in(row: dict, contract: dict) -> float:
    """All-in total in the contract currency (meaningful for qualified rows)."""
    return _sum_parts(row, normalize_contract(contract))


def lower_bound(row: dict, contract: dict) -> float:
    """Lowest possible all-in total: unknown parts count as 0. Never a price."""
    return _sum_parts(row, normalize_contract(contract))


# --------------------------------------------------------------------------- storage

def resolve_run_dir(arg: str | None) -> str:
    if arg:
        if not os.path.isfile(os.path.join(arg, "contract.json")):
            raise UsageError(f"no run at {arg}; create one with: run_log.py init --contract FILE")
        return arg
    root = runs_root()
    candidates = []
    if os.path.isdir(root):
        for name in os.listdir(root):
            path = os.path.join(root, name)
            if os.path.isfile(os.path.join(path, "contract.json")):
                candidates.append((os.path.getmtime(path), path))
    if not candidates:
        raise UsageError(f"no run found under {root}; create one with: run_log.py init --contract FILE")
    return max(candidates)[1]


def load_run(run_dir: str) -> tuple[dict, list[dict]]:
    with open(os.path.join(run_dir, "contract.json"), encoding="utf-8") as handle:
        contract = json.load(handle)
    records = []
    with open(os.path.join(run_dir, "rows.jsonl"), encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                records.append(json.loads(line))
    return contract, records


def append_record(run_dir: str, record: dict) -> None:
    with open(os.path.join(run_dir, "rows.jsonl"), "a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def _superseded(records: list[dict]) -> set[str]:
    return {r["supersedes"] for r in records if r.get("type") == "row" and r.get("supersedes")}


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


def cmd_add(args) -> int:
    run_dir = resolve_run_dir(args.run)
    row = _read_json(args.row)
    contract, records = load_run(run_dir)
    errors = validate_row(row, contract)
    ids = {r["id"] for r in records if r.get("type") == "row"}
    if isinstance(row, dict) and row.get("supersedes") and row["supersedes"] not in ids:
        errors.append(f"supersedes names {row['supersedes']}, which is not in this run")
    if errors:
        raise UsageError("invalid row (nothing saved):\n" + "\n".join(f"  - {e}" for e in errors))
    row_id = f"r{len(ids) + 1}"
    record = dict(row, type="row", id=row_id,
                  added_at=datetime.now().astimezone().isoformat(timespec="seconds"))
    append_record(run_dir, record)
    status, reasons = row_status(record, contract, _superseded(records + [record]))
    print(f"{row_id} {status}" + (": " + "; ".join(reasons) if reasons else ""))
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("init", help="validate a contract and create a run")
    p.add_argument("--contract", required=True, help="contract JSON file, or - for stdin")
    p.add_argument("--runs-root", help="directory holding runs (default: see module docstring)")
    p.set_defaults(func=cmd_init)
    p = sub.add_parser("add", help="append one observation row (saved immediately)")
    p.add_argument("--row", required=True, help="row JSON file, or - for stdin")
    p.add_argument("--run", help="run directory (default: most recent run)")
    p.set_defaults(func=cmd_add)
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
