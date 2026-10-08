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
import contextlib
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
    cabin_bags = bags.get("cabin_per_person", 0) if isinstance(bags, dict) else 0
    if not isinstance(cabin_bags, int) or isinstance(cabin_bags, bool) or cabin_bags < 0:
        errors.append("bags.cabin_per_person must be an integer >= 0 (full-size cabin bags per person)")
    if isinstance(travelers, dict):
        ages = travelers.get("children_ages", [])
        if not isinstance(ages, list) or any(not isinstance(a, int) or isinstance(a, bool) or a < 0 for a in ages):
            errors.append("travelers.children_ages must be a list of ages (integers)")
        infants = travelers.get("infants", 0)
        if not isinstance(infants, int) or isinstance(infants, bool) or infants < 0:
            errors.append("travelers.infants must be an integer >= 0")
    for key in ("nearby_origins", "alt_destinations"):
        value = contract.get(key, [])
        if not isinstance(value, list) or not all(isinstance(v, str) and v for v in value):
            errors.append(f"{key} must be a list of airport codes")
    positioning = contract.get("positioning", {})
    if positioning is not None and (not isinstance(positioning, dict) or any(
            not isinstance(positioning.get(k, False), bool) for k in ("allowed", "rail_ok", "overnight_ok"))):
        errors.append("positioning must be an object with true/false allowed, rail_ok, overnight_ok")
    if not isinstance(contract.get("self_transfer_ok", False), bool):
        errors.append("self_transfer_ok must be true or false")
    hacks = contract.get("hacks")
    if hacks is not None and (not isinstance(hacks, list) or any(h not in HACKS for h in hacks)):
        errors.append(f"hacks must be drawn from {', '.join(HACKS)}")
    elif hacks and contract.get("scope") == "quick" and any(h != "nearby_origin" for h in hacks):
        errors.append("a quick scope tests only nearby_origin; use scope full to compare other hacks")
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
    c["bags"].setdefault("cabin_per_person", 0)
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


def _origin_pool(c: dict, hack) -> list[str]:
    """Departure airports a row with this hack may use."""
    nearby = c["nearby_origins"] if c["positioning"]["allowed"] else []
    if hack == "nearby_origin":
        return list(c["nearby_origins"])
    if hack == "open_jaw":
        return list(dict.fromkeys(c["origins"] + nearby))
    return list(c["origins"])


def _destination_pool(c: dict, hack) -> list[str]:
    """Arrival airports a row with this hack may use."""
    if hack == "alt_destination":
        return list(c["alt_destinations"])
    if hack == "open_jaw":
        return list(dict.fromkeys(c["destinations"] + c["alt_destinations"]))
    return list(c["destinations"])


def _hack_auto(contract: dict, hack: str):
    def na(reason):
        return {"as": "na", "reason": reason}

    if hack in ("split", "open_jaw") and contract["trip_type"] == "one_way":
        return na("one-way trip")
    if hack == "open_jaw" and len(_origin_pool(contract, "open_jaw")) < 2 \
            and len(_destination_pool(contract, "open_jaw")) < 2:
        return na("no other airport to open the jaw")
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
        if row.get("cabin") and row["cabin"] not in normalize_contract(contract)["cabins"]:
            errors.append("cabin not requested: this attempt is for a cabin outside the run's contract")
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
        if t.get("cabin_bag") is not None and t["cabin_bag"] not in BAGGAGE:
            errors.append(f"tickets[{n}].cabin_bag must be one of {', '.join(BAGGAGE)}")
        if t.get("cabin_bag_fee") is not None and (not _is_number(t["cabin_bag_fee"]) or t["cabin_bag_fee"] < 0):
            errors.append(f"tickets[{n}].cabin_bag_fee must be null or a non-negative number")
    directions = row.get("directions")
    if "directions" in row and not isinstance(directions, list):
        errors.append("directions must be a list")
    for n, d in enumerate(directions if isinstance(directions, list) else [], 1):
        if not isinstance(d, dict):
            errors.append(f"directions[{n}] must be an object")
            continue
        if d.get("dir") not in ("out", "ret"):
            errors.append(f"directions[{n}].dir must be out or ret (a stopover uses several out or ret legs)")
        if d.get("duration") is not None:
            try:
                duration_to_seconds(d["duration"])
            except ValueError:
                errors.append(f"directions[{n}].duration must be HH:MM:SS, or null if not shown")
        if d.get("stops") is not None and (not isinstance(d["stops"], int) or isinstance(d["stops"], bool)
                                           or d["stops"] < 0):
            errors.append(f"directions[{n}].stops must be an integer >= 0")
        errors.extend(f"directions[{n}].{k} must be true or false" for k in ("airport_change", "self_transfer")
                      if k in d and not isinstance(d[k], bool))
        errors.extend(f"directions[{n}].{k} must be an airport-local timestamp string" for k in ("dep", "arr")
                      if d.get(k) is not None and not isinstance(d[k], str))
    components = row.get("components") or {}
    if not isinstance(components, dict):
        errors.append("components must be an object")
    else:
        errors.extend(f"components.{k} must be null or a non-negative number" for k, v in components.items()
                      if v is not None and (not _is_number(v) or v < 0))
    fx = row.get("fx")
    if fx is not None and (not isinstance(fx, dict) or not _is_number(fx.get("rate")) or fx["rate"] <= 0):
        errors.append("fx must be null or {\"rate\": number > 0, \"date\": ..., \"source\": ...}")
    if not errors:
        c = normalize_contract(contract)
        mismatch = _contract_mismatch(row, c)
        errors.extend(f"{m}: this row describes a different search than the run's contract" for m in mismatch)
        if mismatch and row.get("hack"):
            errors.append(f"record a {row['hack']} as one row per combination: every ticket of the combination, "
                          "out and ret directions, and the run's date pair")
    return errors


def row_cell_id(row: dict) -> str:
    if row.get("hack"):
        return f"{row.get('cabin')}/hack/{row['hack']}"
    return baseline_cell_id(row.get("cabin"), row.get("origin"), row.get("destination"),
                            row.get("outbound_date"), row.get("return_date"))


def _contract_mismatch(row: dict, c: dict) -> list[str]:
    """Reasons a populated row describes a different search than the contract."""
    reasons = []
    if row.get("cabin") not in c["cabins"]:
        reasons.append("cabin not requested")
    pair = [row.get("outbound_date"), row.get("return_date") if c["trip_type"] == "return" else None]
    if pair not in expand_dates(c["dates"], c["trip_type"]):
        reasons.append("dates not in contract")
    if row.get("origin") not in _origin_pool(c, row.get("hack")):
        reasons.append("origin not in contract")
    if row.get("destination") not in _destination_pool(c, row.get("hack")):
        reasons.append("destination not in contract")
    return reasons


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
    reasons.extend(_contract_mismatch(row, c))
    hack = row.get("hack")
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
    if c["bags"]["cabin_per_person"] > 0:
        if any(t.get("cabin_bag") in (None, "unverified") for t in tickets):
            reasons.append("cabin bag unverified")
        if any(t.get("cabin_bag") == "fee_required" and t.get("cabin_bag_fee") is None for t in tickets):
            reasons.append("cabin bag fee unknown")
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
    if c["bags"]["cabin_per_person"] > 0:
        bags += sum(t.get("cabin_bag_fee") or 0 for t in tickets if t.get("cabin_bag") == "fee_required")
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


def risk_flags(row: dict, contract: dict) -> list[str]:
    """Practicality flags shown beside a ranked option (not gates)."""
    dirs = row.get("directions") or []
    components = row.get("components") or {}
    flags = []
    label = row.get("cabin_label") or ""
    if "+" in label:
        flags.append(f"mixed cabin: {label}")
    if any(d.get("airport_change") for d in dirs):
        flags.append("airport change")
    if any(str(d.get("arr") or "")[:10] > str(d.get("dep") or "")[:10] for d in dirs if d.get("arr") and d.get("dep")):
        flags.append("next-day arrival")
    if len(row.get("tickets") or []) > 1:
        flags.append("separate tickets")
    if any((d.get("stops") or 0) >= 2 for d in dirs):
        flags.append("2+ stops")
    if any(d.get("self_transfer") for d in dirs):
        flags.append("self-transfer")
    flags.extend(name for name in ("positioning", "hotel") if name in components)
    return flags


def _row_id_key(row_id: str):
    return int(row_id[1:]) if row_id[1:].isdigit() else 0


def _travel_key(row: dict) -> tuple[int, int]:
    seconds, stops = [], 0
    for d in row.get("directions") or []:
        try:
            seconds.append(duration_to_seconds(d.get("duration")))
        except ValueError:
            pass
        stops += d.get("stops") or 0
    return max(seconds, default=0), stops


def evaluate(contract: dict, records: list[dict]) -> list[dict]:
    """Status, totals and flags for every row record, in log order."""
    superseded = _superseded(records)
    out = []
    for r in records:
        if r.get("type") != "row":
            continue
        status, reasons = row_status(r, contract, superseded)
        priced = status in ("qualified", "lead")
        out.append({"id": r["id"], "cabin": r.get("cabin"), "cell": row_cell_id(r), "status": status,
                    "reasons": reasons,
                    "all_in": all_in(r, contract) if status == "qualified" else None,
                    "lower_bound": lower_bound(r, contract) if priced else None,
                    "flags": risk_flags(r, contract) if priced else [], "row": r})
    return out


def _comparable(row: dict, contract: dict) -> bool:
    """A lead's lower bound is in the contract currency (same currency, or fx recorded)."""
    return row.get("currency") == contract["currency"] or bool(row.get("fx"))


def rank(contract: dict, records: list[dict], cabin: str | None = None) -> dict:
    """Qualified options by all-in total, and leads with their pruning state, per cabin."""
    evaluated = evaluate(contract, records)
    cabins = [cabin] if cabin else list(contract["cabins"])
    result = {}
    for cab in cabins:
        qualified = sorted((e for e in evaluated if e["cabin"] == cab and e["status"] == "qualified"),
                           key=lambda e: (e["all_in"], *_travel_key(e["row"]), _row_id_key(e["id"])))
        best = qualified[0]["all_in"] if qualified else None
        leads = []
        for e in evaluated:
            if e["cabin"] != cab or e["status"] != "lead":
                continue
            comparable = _comparable(e["row"], contract)
            currency = contract["currency"] if comparable else e["row"].get("currency")
            leads.append(dict(e, comparable=comparable, currency=currency,
                              pruned=comparable and best is not None and e["lower_bound"] >= best))
        leads.sort(key=lambda e: (not e["comparable"], e["lower_bound"], _row_id_key(e["id"])))
        result[cab] = {"best": best, "qualified": qualified, "leads": leads}
    return result


def _plural_families(n: int) -> str:
    return f"{n} source family attempted" if n == 1 else f"{n} source families attempted"


def cell_states(contract: dict, records: list[dict]) -> list[dict]:
    """Open/done/resolved state of every expected comparison."""
    cells = contract.get("cells") or build_cells(contract)
    every = evaluate(contract, records)  # superseded rows still prove a family was searched
    evaluated = [e for e in every if e["status"] != "superseded"]
    ranked = rank(contract, records)
    pruned = {lead["id"]: lead["pruned"] for v in ranked.values() for lead in v["leads"]}
    resolutions = {}
    for r in records:
        if r.get("type") == "resolve":
            resolutions[r["cell"]] = f"{r['as']}: {r['reason']}"
    states = []
    for cell in cells:
        cab = cell["cabin"]
        in_cell = [e for e in evaluated if e["cell"] == cell["id"]]
        in_cabin = [e for e in evaluated if e["cabin"] == cab]
        populated = [e for e in in_cell if e["status"] != "attempt"]
        if cell["id"] in resolutions:
            state, why = "resolved", resolutions[cell["id"]]
        elif cell.get("auto"):
            state, why = "resolved", f"{cell['auto']['as']}: {cell['auto']['reason']}"
        elif cell["kind"] == "crosscheck":
            n = len({e["row"].get("family") for e in every if e["cabin"] == cab})
            state, why = ("done", "") if n >= 2 else ("open", _plural_families(n))
            in_cell = in_cabin
        elif cell["kind"] == "reprice":
            ok = any(e["status"] == "qualified" for e in in_cabin)
            state, why = ("done", "") if ok else ("open", "no qualified option")
            in_cell = [e for e in in_cabin if e["status"] == "qualified"]
        elif not in_cell:
            state, why = "open", "not attempted"
        elif not populated:
            state, why = "open", "only blocked/empty/error attempts"
        elif cell["kind"] == "baseline" or any(e["status"] == "qualified" for e in populated):
            state, why = "done", ""
        else:
            unresolved = [e["id"] for e in populated if e["status"] == "lead" and not pruned.get(e["id"])]
            state, why = ("open", f"unresolved lead(s): {', '.join(unresolved)}") if unresolved else ("done", "")
        states.append({"id": cell["id"], "kind": cell["kind"], "cabin": cab, "state": state,
                       "why": why, "rows": len(in_cell)})
    return states


def check(contract: dict, records: list[dict]) -> dict:
    """Is the run complete? Lists open comparisons, closed-without-result cells and warnings."""
    states = cell_states(contract, records)
    warn = []
    every = evaluate(contract, records)
    cur = contract["currency"]
    for cab, v in rank(contract, records).items():
        for lead in v["leads"]:
            if not lead["comparable"]:
                if v["best"] is not None:
                    warn.append(f"{cab}: lead {lead['id']} is priced in {lead['currency']} without fx; "
                                f"not comparable with best qualified ({v['best']:.2f} {cur})")
            elif v["best"] is not None and not lead["pruned"]:
                warn.append(f"{cab}: lead {lead['id']} may beat best qualified "
                            f"(LB {lead['lower_bound']:.2f} < {v['best']:.2f})")
        if v["best"] is None and v["leads"]:
            warn.append(f"{cab}: no qualified option; {len(v['leads'])} lead(s) unverified")
        families = sorted({e["row"].get("family") for e in every
                           if e["cabin"] == cab and e["row"].get("outcome", "populated") == "populated"})
        if not families:
            warn.append(f"{cab}: no source family returned results")
        elif len(families) == 1:
            warn.append(f"{cab}: only one source family returned results ({families[0]})")
    open_items = [{"cell": s["id"], "why": s["why"]} for s in states if s["state"] == "open"]
    return {"complete": not open_items, "open": open_items,
            "resolved": [{"cell": s["id"], "why": s["why"]} for s in states if s["state"] == "resolved"],
            "warn": warn}


# --------------------------------------------------------------------------- storage

def resolve_run_dir(arg: str | None) -> str:
    """The --run directory, else the most recently used run; reported on stderr."""
    run_dir = _find_run_dir(arg)
    print(f"run: {run_dir}", file=sys.stderr)
    return run_dir


def _find_run_dir(arg: str | None) -> str:
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
    with open(os.path.join(run_dir, "rows.jsonl"), encoding="utf-8") as handle:
        lines = [(n, line) for n, line in enumerate(handle.read().split("\n"), 1) if line.strip()]
    records = []
    for i, (n, line) in enumerate(lines):
        try:
            records.append(json.loads(line))
        except ValueError:
            if i == len(lines) - 1:
                print(f"warning: ignoring truncated last line {n} of rows.jsonl", file=sys.stderr)
                continue
            raise ValueError(f"rows.jsonl line {n} is not valid JSON; repair or remove it")
    return contract, records


def _trim_partial_tail(path: str) -> None:
    """Drop an unterminated last line left by an interrupted write."""
    with open(path, "rb+") as handle:
        data = handle.read()
        if data and not data.endswith(b"\n"):
            keep = data.rfind(b"\n") + 1
            handle.seek(keep)
            handle.truncate()
            print("warning: removed a truncated last line from rows.jsonl", file=sys.stderr)


@contextlib.contextmanager
def locked(run_dir: str):
    """Hold an exclusive lock on the run while reading, numbering and appending."""
    with open(os.path.join(run_dir, ".lock"), "a+") as handle:
        try:
            import fcntl
        except ImportError:  # Windows
            import msvcrt
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
            try:
                yield
            finally:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            return
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def append_record(run_dir: str, record: dict) -> None:
    path = os.path.join(run_dir, "rows.jsonl")
    _trim_partial_tail(path)
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.utime(run_dir)  # the default run is the most recently used one


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
    with locked(run_dir):
        return _add(run_dir, row)


def _add(run_dir: str, row) -> int:
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


def _public(entry: dict) -> dict:
    row = entry["row"]
    out = {k: v for k, v in entry.items() if k != "row"}
    out.update({"source": row.get("source"), "family": row.get("family"), "url": row.get("url"),
                "retrieved_at": row.get("retrieved_at"), "hack": row.get("hack"),
                "booking_urls": [t.get("booking_url") for t in row.get("tickets") or [] if t.get("booking_url")]})
    return out


def cmd_rank(args) -> int:
    contract, records = load_run(resolve_run_dir(args.run))
    if args.cabin and args.cabin not in contract["cabins"]:
        raise UsageError(f"cabin {args.cabin} is not in this run's contract")
    ranked = rank(contract, records, args.cabin)
    if args.json:
        print(json.dumps({cab: {"best": v["best"], "qualified": [_public(e) for e in v["qualified"]],
                                "leads": [_public(e) for e in v["leads"]]} for cab, v in ranked.items()},
                         indent=2, ensure_ascii=False))
        return EXIT_OK
    cur = contract["currency"]
    for cab, v in ranked.items():
        print(f"== {cab}: qualified (all-in {cur})")
        for n, e in enumerate(v["qualified"], 1):
            row = e["row"]
            hack = f" [{row['hack']}]" if row.get("hack") else ""
            flags = f"  flags: {', '.join(e['flags'])}" if e["flags"] else ""
            print(f"  {n}. {e['id']}{hack} {e['all_in']:.2f} {row.get('source')} {row.get('retrieved_at')}{flags}")
        if not v["qualified"]:
            print("  (none)")
        print(f"== {cab}: leads (not verified; lower bound, never a price)")
        for e in v["leads"]:
            row = e["row"]
            hack = f" [{row['hack']}]" if row.get("hack") else ""
            pruned = f"  pruned: LB {e['lower_bound']:.2f} >= best {v['best']:.2f}" if e["pruned"] else ""
            note = "" if e["comparable"] else "  (no fx: not comparable)"
            print(f"  {e['id']}{hack} LB {e['lower_bound']:.2f} {e['currency']}: "
                  f"{'; '.join(e['reasons'])}{pruned}{note}")
        if not v["leads"]:
            print("  (none)")
    return EXIT_OK


def _resolve_guard(cell: dict, kind: str, contract: dict, records: list[dict]) -> str | None:
    """Why this resolution is not allowed, or None."""
    rows = [e for e in evaluate(contract, records) if e["status"] != "superseded"]
    if kind == "no_fare":
        if cell["kind"] not in ("baseline", "hack"):
            return "no_fare closes a baseline or hack comparison only"
        searched = [e for e in rows if e["cell"] == cell["id"]
                    and (e["status"] != "attempt" or e["row"].get("outcome") == "empty")]
        if not searched:
            return ("no_fare needs an executed search in this cell: add the empty or populated result first "
                    "(blocked or error attempts are not a search)")
    if kind == "none_qualify":
        if cell["kind"] != "reprice":
            return "none_qualify closes a cabin's reprice comparison only"
        if not any(e["cabin"] == cell["cabin"] and e["status"] != "attempt" for e in rows):
            return "none_qualify needs at least one priced candidate in this cabin"
    return None


def cmd_resolve(args) -> int:
    run_dir = resolve_run_dir(args.run)
    with locked(run_dir):
        contract, records = load_run(run_dir)
        cells = {c["id"]: c for c in contract.get("cells") or build_cells(contract)}
        if args.cell not in cells:
            raise UsageError(f"unknown cell {args.cell}; see run_log.py coverage")
        refusal = _resolve_guard(cells[args.cell], getattr(args, "as"), contract, records)
        if refusal:
            raise UsageError(refusal)
        append_record(run_dir, {"type": "resolve", "cell": args.cell, "as": getattr(args, "as"),
                                "reason": args.reason,
                                "at": datetime.now().astimezone().isoformat(timespec="seconds")})
    print(f"resolved {args.cell} as {getattr(args, 'as')}: {args.reason}")
    return EXIT_OK


def cmd_coverage(args) -> int:
    contract, records = load_run(resolve_run_dir(args.run))
    states = cell_states(contract, records)
    if args.json:
        print(json.dumps(states, indent=2, ensure_ascii=False))
        return EXIT_OK
    for s in states:
        print(f"{s['state']:<9}{s['id']}  rows={s['rows']}  {s['why']}".rstrip())
    closed = sum(1 for s in states if s["state"] != "open")
    print(f"{closed}/{len(states)} cells closed")
    return EXIT_OK


def cmd_check(args) -> int:
    contract, records = load_run(resolve_run_dir(args.run))
    result = check(contract, records)
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print("COMPLETE" if result["complete"] else f"INCOMPLETE: {len(result['open'])} open item(s)")
        for item in result["open"]:
            print(f"OPEN      {item['cell']}  {item['why']}")
        for item in result["resolved"]:
            print(f"RESOLVED  {item['cell']}  {item['why']}")
        for msg in result["warn"]:
            print(f"WARN      {msg}")
    return EXIT_OK if result["complete"] else EXIT_INCOMPLETE


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
    p = sub.add_parser("rank", help="qualified options by all-in total, then leads")
    p.add_argument("--run", help="run directory (default: most recent run)")
    p.add_argument("--cabin", help="only this cabin")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_rank)
    p = sub.add_parser("resolve", help="close a comparison that legitimately has no qualified row")
    p.add_argument("cell", help="cell id from coverage")
    p.add_argument("--as", required=True, choices=("na", "no_fare", "none_qualify"))
    p.add_argument("--reason", required=True)
    p.add_argument("--run", help="run directory (default: most recent run)")
    p.set_defaults(func=cmd_resolve)
    p = sub.add_parser("coverage", help="expected comparisons and their state")
    p.add_argument("--run", help="run directory (default: most recent run)")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_coverage)
    p = sub.add_parser("check", help="exit 0 when complete, 4 while comparisons are open")
    p.add_argument("--run", help="run directory (default: most recent run)")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_check)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (UsageError, ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_USAGE
    except Exception as exc:  # malformed data in a hand-edited log; never a traceback
        print(f"error: unexpected {type(exc).__name__}: {exc}. rows.jsonl may hold a malformed row; "
              "fix or remove it and run the command again", file=sys.stderr)
        return EXIT_USAGE


if __name__ == "__main__":
    sys.exit(main())
