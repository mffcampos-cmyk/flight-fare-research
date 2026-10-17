"""Observation rows for the flight-fare-research skill (stdlib only, no network).

A fare row is one bookable combination for one date tuple: its tickets, one
entry per flown leg, the all-in parts. A ground row prices the train, bus or
flight between a home airport and a nearby one. This module validates rows,
computes each row's status (the agent never asserts it), ranks qualified rows
and decides whether a run is complete. `run_log.py` stores the rows.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from ffr_contract import (HACKS, IATA, airports, duration_to_seconds, home_airport, tuple_id,
                          via_airports)

OUTCOMES = ("populated", "blocked", "empty", "error")
QUOTE_STATES = ("list", "completed", "repriced")
BAGGAGE = ("included", "fee_required", "unverified")
PRICE_BASES = ("total", "per_person")
PHASES = ("discover", "exact")
ATTEMPT_FIELDS = ("source", "family", "engine", "outcome", "url", "retrieved_at", "cabin")
POPULATED_FIELDS = ("currency", "origin", "destination", "dates", "tickets", "legs")
GROUND_FIELDS = ("source", "engine", "url", "retrieved_at", "from", "to", "date", "price", "currency", "quote_state")


def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value == value


def _is_int(value, minimum=0) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= minimum


def _is_date(value) -> bool:
    try:
        return isinstance(value, str) and date.fromisoformat(value) is not None
    except ValueError:
        return False


def _stamp_errors(stamp, field="retrieved_at") -> list[str]:
    if stamp in (None, ""):
        return []
    try:
        if datetime.fromisoformat(str(stamp)).tzinfo is None:
            return [f"{field} needs a timezone offset, e.g. 2026-10-08T14:03:00+02:00"]
    except ValueError:
        return [f"{field} must be an ISO 8601 timestamp with a timezone offset"]
    return []


# --------------------------------------------------------------------------- validation

def validate_row(row: dict, contract: dict) -> list[str]:
    """Problems with a fare row or attempt against a normalized contract; [] when valid."""
    if not isinstance(row, dict):
        return ["row must be a JSON object"]
    errors = [f"{field} is required" for field in ATTEMPT_FIELDS if row.get(field) in (None, "")]
    if row.get("outcome") not in (None, "") and row["outcome"] not in OUTCOMES:
        errors.append(f"outcome must be one of {', '.join(OUTCOMES)}")
    errors.extend(_stamp_errors(row.get("retrieved_at")))
    if row.get("hack") is not None and row["hack"] not in HACKS:
        errors.append(f"hack must be null or one of {', '.join(HACKS)}")
    if row.get("phase", "exact") not in PHASES:
        errors.append(f"phase must be one of {', '.join(PHASES)}")
    if row.get("price_basis", "total") not in PRICE_BASES:
        errors.append(f"price_basis must be one of {', '.join(PRICE_BASES)}")
    if row.get("cabin") and row["cabin"] not in contract["cabins"]:
        errors.append("cabin not requested: this row is for a cabin outside the run's contract")
    if row.get("outcome") != "populated":
        return errors
    errors.extend(f"{field} is required for a populated row" for field in POPULATED_FIELDS
                  if field not in row or row[field] in (None, ""))
    tickets = row.get("tickets")
    if "tickets" in row and (not isinstance(tickets, list) or not tickets):
        errors.append("tickets must be a non-empty list")
    for n, t in enumerate(tickets if isinstance(tickets, list) else [], 1):
        errors.extend(_ticket_errors(t, n))
    legs = row.get("legs")
    if "legs" in row and (not isinstance(legs, list) or not legs):
        errors.append("legs must be a non-empty list")
    for n, d in enumerate(legs if isinstance(legs, list) else [], 1):
        errors.extend(_leg_errors(d, n, len(contract["legs"])))
    dates = row.get("dates")
    if dates is not None and (not isinstance(dates, list) or not all(_is_date(d) for d in dates)):
        errors.append("dates must be a list of YYYY-MM-DD dates, one per contract leg")
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
        errors.extend(f"{m}: this row describes a different search than the run's contract"
                      for m in _contract_mismatch(row, contract))
    return errors


def _ticket_errors(t, n: int) -> list[str]:
    if not isinstance(t, dict):
        return [f"tickets[{n}] must be an object"]
    errors = []
    if not _is_number(t.get("price")) or t["price"] < 0:
        errors.append(f"tickets[{n}].price must be a non-negative number (no currency text)")
    if t.get("quote_state") not in QUOTE_STATES:
        errors.append(f"tickets[{n}].quote_state must be one of {', '.join(QUOTE_STATES)}")
    if t.get("baggage") not in BAGGAGE:
        errors.append(f"tickets[{n}].baggage must be one of {', '.join(BAGGAGE)}")
    for key in ("bag_fee", "cabin_bag_fee"):
        if t.get(key) is not None and (not _is_number(t[key]) or t[key] < 0):
            errors.append(f"tickets[{n}].{key} must be null or a non-negative number")
    if t.get("cabin_bag") is not None and t["cabin_bag"] not in BAGGAGE:
        errors.append(f"tickets[{n}].cabin_bag must be one of {', '.join(BAGGAGE)}")
    return errors


def _leg_errors(d, n: int, n_legs: int) -> list[str]:
    if not isinstance(d, dict):
        return [f"legs[{n}] must be an object"]
    errors = []
    if not _is_int(d.get("leg"), 1) or d["leg"] > n_legs:
        errors.append(f"legs[{n}].leg must be a contract leg number (1..{n_legs})")
    if not _is_int(d.get("part", 1), 1):
        errors.append(f"legs[{n}].part must be an integer >= 1 (a stopover splits one leg into parts)")
    for key in ("from", "to"):
        if not isinstance(d.get(key), str) or not IATA.match(d[key]):
            errors.append(f"legs[{n}].{key} must be a three-letter airport code")
    if d.get("duration") is not None:
        try:
            duration_to_seconds(d["duration"])
        except ValueError:
            errors.append(f"legs[{n}].duration must be HH:MM:SS, or null if not shown")
    if d.get("stops") is not None and not _is_int(d["stops"]):
        errors.append(f"legs[{n}].stops must be an integer >= 0")
    errors.extend(f"legs[{n}].{k} must be true or false" for k in ("airport_change", "self_transfer")
                  if k in d and not isinstance(d[k], bool))
    errors.extend(f"legs[{n}].{k} must be an airport-local timestamp string" for k in ("dep", "arr")
                  if d.get(k) is not None and not isinstance(d[k], str))
    if d.get("airlines") is not None and (not isinstance(d["airlines"], list)
                                          or any(not isinstance(a, str) for a in d["airlines"])):
        errors.append(f"legs[{n}].airlines must be a list of airline codes")
    return errors


def validate_ground(row: dict, contract: dict) -> list[str]:
    """Problems with a ground row (kind "ground") against a normalized contract."""
    if not isinstance(row, dict):
        return ["ground row must be a JSON object"]
    errors = [f"{field} is required for a ground row" for field in GROUND_FIELDS if row.get(field) in (None, "")]
    errors.extend(_stamp_errors(row.get("retrieved_at")))
    if row.get("price") is not None and (not _is_number(row["price"]) or row["price"] < 0):
        errors.append("price must be a non-negative number")
    if row.get("quote_state") not in (None, "") and row["quote_state"] not in QUOTE_STATES:
        errors.append(f"quote_state must be one of {', '.join(QUOTE_STATES)}")
    if row.get("date") not in (None, "") and not _is_date(row["date"]):
        errors.append("date must be YYYY-MM-DD")
    if errors:
        return errors
    pair = {row["from"], row["to"]}
    vias = via_airports(contract)
    homes = {home_airport(lg[side]) for lg in contract["legs"] for side in ("from", "to")}
    if not (pair & set(vias)) or not (pair & (homes | set(vias))):
        errors.append(f"{row['from']}-{row['to']} is not a ground leg between a home airport and a nearby airport "
                      f"of this contract (nearby: {', '.join(sorted(vias)) or 'none'})")
    return errors


# --------------------------------------------------------------------------- cells and gates

def row_cell_id(row: dict, contract: dict) -> str:
    """The comparison cell a row belongs to."""
    cabin = row.get("cabin")
    if row.get("hack"):
        return f"{cabin}/hack/{row['hack']}"
    if contract.get("speed") == "fast":
        kind = "discover" if row.get("phase", "exact") == "discover" else "confirm"
        return f"{cabin}/{kind}/{row.get('destination')}"
    return f"{cabin}/baseline/{row.get('origin')}-{row.get('destination')}/{tuple_id(row.get('dates') or [])}"


def _contract_mismatch(row: dict, c: dict) -> list[str]:
    """Reasons a populated row describes a different search than the contract."""
    reasons = []
    if row.get("cabin") not in c["cabins"]:
        reasons.append("cabin not requested")
    tuples = c.get("date_tuples")
    if tuples is None:
        from ffr_contract import expand_tuples
        tuples = expand_tuples(c)
    if list(row.get("dates") or []) not in tuples:
        reasons.append("dates not in contract")
    by_leg = {}
    for d in row.get("legs") or []:
        by_leg.setdefault(d.get("leg"), []).append(d)
    for n, parts in sorted(by_leg.items(), key=lambda kv: (kv[0] is None, kv[0])):
        if not isinstance(n, int) or n < 1 or n > len(c["legs"]):
            continue
        lg = c["legs"][n - 1]
        parts = sorted(parts, key=lambda d: d.get("part", 1))
        first, last = parts[0].get("from"), parts[-1].get("to")
        if first not in airports(lg["from"]):
            reasons.append(f"leg {n}: origin {first} not in contract")
        if last not in airports(lg["to"]):
            reasons.append(f"leg {n}: destination {last} not in contract")
    if 1 in by_leg:
        if row.get("origin") != sorted(by_leg[1], key=lambda d: d.get("part", 1))[0].get("from"):
            reasons.append(f"leg 1: origin {row.get('origin')} not in contract")
    elif row.get("origin") not in airports(c["legs"][0]["from"]):
        reasons.append(f"leg 1: origin {row.get('origin')} not in contract")
    if row.get("destination") not in airports(c["legs"][0]["to"]):
        reasons.append(f"leg 1: destination {row.get('destination')} not in contract")
    return list(dict.fromkeys(reasons))


def _clock(stamp) -> str | None:
    return str(stamp)[11:16] if isinstance(stamp, str) and len(stamp) >= 16 else None


def _leg_label(d: dict) -> str:
    part = d.get("part", 1)
    return f"leg {d.get('leg')}" + (f" part {part}" if part and part > 1 else "")


def hard_gate_reasons(row: dict, c: dict) -> list[str]:
    reasons = []
    cap = c.get("max_duration")
    windows = {w["leg"]: w for w in c.get("time_windows") or []}
    excluded = set(c["airlines"].get("exclude") or [])
    for d in row.get("legs") or []:
        label = _leg_label(d)
        if cap:
            limit = duration_to_seconds(cap["value"])
            kind = "strict" if cap["strict"] else "inclusive"
            try:
                seconds = duration_to_seconds(d.get("duration"))
            except ValueError:
                seconds = None
            if seconds is not None and (seconds > limit or (cap["strict"] and seconds == limit)):
                reasons.append(f"{label} duration {d['duration']} breaks {kind} cap {cap['value']}")
        if c.get("max_stops") is not None and (d.get("stops") or 0) > c["max_stops"]:
            reasons.append(f"{label} stops {d.get('stops')} over max {c['max_stops']}")
        w = windows.get(d.get("leg"))
        if w:
            dep, arr = _clock(d.get("dep")), _clock(d.get("arr"))
            if dep and w.get("dep_after") and dep < w["dep_after"]:
                reasons.append(f"{label} departs {dep} before {w['dep_after']}")
            if dep and w.get("dep_before") and dep > w["dep_before"]:
                reasons.append(f"{label} departs {dep} after {w['dep_before']}")
            if arr and w.get("arr_after") and arr < w["arr_after"]:
                reasons.append(f"{label} arrives {arr} before {w['arr_after']}")
            if arr and w.get("arr_before") and arr > w["arr_before"]:
                reasons.append(f"{label} arrives {arr} after {w['arr_before']}")
        for airline in d.get("airlines") or []:
            if airline in excluded:
                reasons.append(f"{label} airline {airline} excluded")
        if d.get("self_transfer") and not c["self_transfer_ok"]:
            reasons.append("self-transfer not allowed")
    reasons.extend(_contract_mismatch(row, c))
    return list(dict.fromkeys(reasons))


# --------------------------------------------------------------------------- ground rows

def _row_dates_by_leg(row: dict) -> dict[int, str]:
    return {n + 1: d for n, d in enumerate(row.get("dates") or [])}


def ground_for(row: dict, c: dict, grounds: list[dict]) -> dict[str, list]:
    """For each nearby airport the row uses, the ground records chosen per use (None when unpriced).

    Returns {code: [record or None, ...]}, one entry per leg end at that airport."""
    vias = via_airports(c)
    dates = _row_dates_by_leg(row)
    out: dict[str, list] = {}
    for d in row.get("legs") or []:
        n = d.get("leg")
        lg = c["legs"][n - 1] if isinstance(n, int) and 1 <= n <= len(c["legs"]) else None
        if not lg:
            continue
        for code, home, day in ((d.get("from"), home_airport(lg["from"]), dates.get(n)),
                                (d.get("to"), home_airport(lg["to"]), str(d.get("arr") or "")[:10] or dates.get(n))):
            if code in vias and code != home:
                out.setdefault(code, []).append(_pick_ground(grounds, code, home, day, vias[code].get("overnight_ok")))
    return out


def _pick_ground(grounds: list[dict], code: str, home: str, day: str | None, overnight_ok: bool):
    if not day:
        return None
    allowed = {day}
    if overnight_ok:
        allowed.add((date.fromisoformat(day) - timedelta(days=1)).isoformat())
        allowed.add((date.fromisoformat(day) + timedelta(days=1)).isoformat())
    matches = [g for g in grounds
               if g.get("quote_state") in ("completed", "repriced") and {g.get("from"), g.get("to")} == {code, home}
               and g.get("date") in allowed and _is_number(g.get("price"))]
    if not matches:
        return None
    return min(matches, key=lambda g: (g["date"] != day, g["price"]))


def lead_reasons(row: dict, c: dict, grounds: list[dict]) -> list[str]:
    reasons = []
    legs = row.get("legs") or []
    present = {d.get("leg") for d in legs}
    for n in range(1, len(c["legs"]) + 1):
        if n not in present:
            reasons.append(f"leg {n} not selected")
    for d in legs:
        try:
            duration_to_seconds(d.get("duration"))
        except ValueError:
            reasons.append(f"duration unknown ({_leg_label(d)})")
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
    for code, chosen in ground_for(row, c, grounds).items():
        if any(g is None for g in chosen):
            reasons.append(f"ground unpriced ({code})")
    reasons.extend(f"{name} unpriced" for name, value in (row.get("components") or {}).items() if value is None)
    if row.get("currency") != c["currency"] and not row.get("fx"):
        reasons.append("currency differs; no fx recorded")
    if row.get("price_basis") == "per_person" and c["travelers"].get("infants"):
        reasons.append("per-person price with infants; record the total")
    return reasons


def row_status(row: dict, contract: dict, superseded: set[str], grounds: list[dict]) -> tuple[str, list[str]]:
    """A row's status and the reasons behind it (never asserted by the agent)."""
    if row.get("id") in superseded:
        return "superseded", []
    if row.get("outcome") != "populated":
        return "attempt", []
    hard = hard_gate_reasons(row, contract)
    if hard:
        return "rejected", hard
    soft = lead_reasons(row, contract, grounds)
    if soft:
        return "lead", soft
    return "qualified", []


# --------------------------------------------------------------------------- totals and flags

def grounds_of(records: list[dict]) -> list[dict]:
    return [r for r in records if r.get("type") == "ground"]


def superseded_ids(records: list[dict]) -> set[str]:
    return {r["supersedes"] for r in records if r.get("type") == "row" and r.get("supersedes")}


def _sum_parts(row: dict, c: dict, grounds: list[dict]) -> float:
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
    for chosen in ground_for(row, c, grounds).values():
        total += sum(g["price"] for g in chosen if g)
    return round(total, 2)


def all_in(row: dict, contract: dict, grounds: list[dict]) -> float:
    """All-in total in the contract currency (meaningful for qualified rows)."""
    return _sum_parts(row, contract, grounds)


def lower_bound(row: dict, contract: dict, grounds: list[dict]) -> float:
    """Lowest possible all-in total: unknown parts count as 0. Never a price."""
    return _sum_parts(row, contract, grounds)


def risk_flags(row: dict, contract: dict, grounds: list[dict]) -> list[str]:
    """Practicality flags shown beside a ranked option (not gates)."""
    legs = row.get("legs") or []
    components = row.get("components") or {}
    flags = []
    label = row.get("cabin_label") or ""
    if "+" in label or "mixed" in label.lower():
        flags.append(f"mixed cabin: {label}")
    if any(d.get("airport_change") for d in legs):
        flags.append("airport change")
    if any(str(d.get("arr") or "")[:10] > str(d.get("dep") or "")[:10] for d in legs if d.get("arr") and d.get("dep")):
        flags.append("next-day arrival")
    if len(row.get("tickets") or []) > 1:
        flags.append("separate tickets")
    if any((d.get("stops") or 0) >= 2 for d in legs):
        flags.append("2+ stops")
    if any(d.get("self_transfer") for d in legs):
        flags.append("self-transfer")
    flags.extend(name for name in ("hotel", "transfers") if name in components)
    prefer = set(contract["airlines"].get("prefer") or [])
    if prefer and legs and all(set(d.get("airlines") or []) & prefer for d in legs):
        flags.append("preferred airline")
    dates = _row_dates_by_leg(row)
    vias = via_airports(contract)
    for code, chosen in ground_for(row, contract, grounds).items():
        for g in chosen:
            if g:
                flags.append(f"ground: {vias[code].get('via') or 'ground'} {g['from']}-{g['to']}")
                if g["date"] not in dates.values():
                    flags.append("overnight before departure")
    if contract.get("budget") is not None and _sum_parts(row, contract, grounds) > contract["budget"]:
        flags.append("over budget")
    return list(dict.fromkeys(flags))


def _row_id_key(row_id: str):
    return int(row_id[1:]) if row_id[1:].isdigit() else 0


def _travel_key(row: dict) -> tuple[int, int]:
    seconds, stops = [], 0
    for d in row.get("legs") or []:
        try:
            seconds.append(duration_to_seconds(d.get("duration")))
        except ValueError:
            pass
        stops += d.get("stops") or 0
    return max(seconds, default=0), stops


# --------------------------------------------------------------------------- evaluate and rank

def evaluate(contract: dict, records: list[dict]) -> list[dict]:
    """Status, totals, flags and ground choices for every fare row, in log order."""
    superseded = superseded_ids(records)
    grounds = grounds_of(records)
    out = []
    for r in records:
        if r.get("type") != "row":
            continue
        status, reasons = row_status(r, contract, superseded, grounds)
        priced = status in ("qualified", "lead")
        out.append({"id": r["id"], "cabin": r.get("cabin"), "cell": row_cell_id(r, contract), "status": status,
                    "reasons": reasons, "phase": r.get("phase", "exact"),
                    "all_in": all_in(r, contract, grounds) if status == "qualified" else None,
                    "lower_bound": lower_bound(r, contract, grounds) if priced else None,
                    "flags": risk_flags(r, contract, grounds) if priced else [],
                    "ground": {code: [g["id"] if g else None for g in chosen]
                               for code, chosen in ground_for(r, contract, grounds).items()} if priced else {},
                    "row": r})
    return out


def public_entry(entry: dict) -> dict:
    """An evaluated entry without the raw row, for JSON output and reports."""
    row = entry["row"]
    tickets = row.get("tickets") or []
    keys = ("leg", "part", "from", "to", "dep", "arr", "duration", "stops", "airlines", "airport_change", "self_transfer")
    out = {k: v for k, v in entry.items() if k != "row"}
    out.update({"source": row.get("source"), "family": row.get("family"), "url": row.get("url"),
                "retrieved_at": row.get("retrieved_at"), "hack": row.get("hack"),
                "origin": row.get("origin"), "destination": row.get("destination"), "dates": row.get("dates"),
                "cabin_label": row.get("cabin_label"), "currency": row.get("currency"),
                "providers": [t.get("provider") for t in tickets if t.get("provider")],
                "legs": [{k: d.get(k) for k in keys} for d in row.get("legs") or [] if isinstance(d, dict)],
                "booking_urls": [t.get("booking_url") for t in tickets if t.get("booking_url")],
                "notes": row.get("notes")})
    return out


def _comparable(row: dict, contract: dict) -> bool:
    return row.get("currency") == contract["currency"] or bool(row.get("fx"))


def rank(contract: dict, records: list[dict], cabin: str | None = None) -> dict:
    """Qualified options by all-in total, and leads with their pruning state, per cabin."""
    evaluated = evaluate(contract, records)
    cabins = [cabin] if cabin else list(contract["cabins"])
    prefer = set(contract["airlines"].get("prefer") or [])
    result = {}
    for cab in cabins:
        qualified = sorted((e for e in evaluated if e["cabin"] == cab and e["status"] == "qualified"),
                           key=lambda e: (e["all_in"], "preferred airline" not in e["flags"] if prefer else 0,
                                          *_travel_key(e["row"]), _row_id_key(e["id"])))
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


# --------------------------------------------------------------------------- completeness

def _plural_families(n: int) -> str:
    return f"{n} source family attempted" if n == 1 else f"{n} source families attempted"


def cell_states(contract: dict, records: list[dict]) -> list[dict]:
    """Open/done/resolved state of every expected comparison."""
    from ffr_contract import build_cells, region_groups
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
        elif cell["kind"] == "confirm":
            state, why = _confirm_state(cell, in_cell)
        elif not in_cell:
            state, why = "open", "not attempted"
        elif not populated:
            state, why = "open", "only blocked/empty/error attempts"
        elif cell["kind"] in ("baseline", "discover") or any(e["status"] == "qualified" for e in populated):
            state, why = "done", ""
        else:
            unresolved = [e["id"] for e in populated if e["status"] == "lead" and not pruned.get(e["id"])]
            state, why = ("open", f"unresolved lead(s): {', '.join(unresolved)}") if unresolved else ("done", "")
        states.append({"id": cell["id"], "kind": cell["kind"], "cabin": cab, "state": state,
                       "why": why, "rows": len(in_cell)})
    for i, side in region_groups(contract):
        name = contract["legs"][i][side]["name"]
        for cab in contract["cabins"]:
            states.append({"id": f"{cab}/discover", "kind": "discover", "cabin": cab, "state": "open",
                           "why": f"region '{name}' has no shortlist: run run_log.py shortlist", "rows": 0})
    return states


def _confirm_state(cell: dict, in_cell: list[dict]) -> tuple[str, str]:
    if not cell.get("tuples"):
        return "open", "no confirm tuples yet: run run_log.py confirm"
    exact = {tuple(e["row"].get("dates") or []) for e in in_cell if e["status"] != "attempt" and e["phase"] == "exact"}
    missing = [tuple_id(t) for t in cell["tuples"] if tuple(t) not in exact]
    if missing:
        return "open", "tuples without an exact-date result: " + ", ".join(missing)
    return "done", ""


def check(contract: dict, records: list[dict]) -> dict:
    """Is the run complete? Lists open comparisons, closed-without-result cells and warnings."""
    states = cell_states(contract, records)
    warn = []
    every = evaluate(contract, records)
    cur = contract["currency"]
    for cab, v in rank(contract, records).items():
        for lead in v["leads"]:
            if not lead["comparable"] and v["best"] is not None:
                warn.append(f"{cab}: lead {lead['id']} is priced in {lead['currency']} without fx; "
                            f"not comparable with best qualified ({v['best']:.2f} {cur})")
        cheaper = [lead for lead in v["leads"] if lead["comparable"] and v["best"] is not None and not lead["pruned"]]
        if cheaper:
            shown = ", ".join(f"{lead['id']} LB {lead['lower_bound']:.2f}" for lead in cheaper[:3])
            more = f" (+{len(cheaper) - 3} more)" if len(cheaper) > 3 else ""
            noun = "lead" if len(cheaper) == 1 else "leads"
            warn.append(f"{cab}: {len(cheaper)} {noun} may beat best qualified {v['best']:.2f} {cur}; "
                        f"cheapest: {shown}{more}")
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


def pick_confirm_tuples(contract: dict, records: list[dict], top: int = 3) -> dict[str, list[list[str]]]:
    """Per cabin and destination, the cheapest `top` date tuples among discovery rows that pass the hard gates."""
    picks: dict[str, list[list[str]]] = {}
    best: dict[tuple, dict[tuple, float]] = {}
    for e in evaluate(contract, records):
        if e["phase"] != "discover" or e["status"] not in ("lead", "qualified") or e["row"].get("hack"):
            continue
        key = (e["cabin"], e["row"].get("destination"))
        dates = tuple(e["row"].get("dates") or [])
        price = e["lower_bound"]
        if dates not in best.setdefault(key, {}) or price < best[key][dates]:
            best[key][dates] = price
    for (cab, dest), by_dates in best.items():
        ordered = sorted(by_dates.items(), key=lambda kv: (kv[1], kv[0]))[:top]
        picks[f"{cab}/{dest}"] = [list(d) for d, _ in ordered]
    return picks


def resolve_guard(cell: dict, kind: str, contract: dict, records: list[dict]) -> str | None:
    """Why this resolution is not allowed, or None."""
    rows = [e for e in evaluate(contract, records) if e["status"] != "superseded"]
    if kind == "no_fare":
        if cell["kind"] not in ("baseline", "hack", "discover", "confirm"):
            return "no_fare closes a baseline, discover, confirm or hack comparison only"
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
