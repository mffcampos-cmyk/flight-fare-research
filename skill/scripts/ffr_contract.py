"""Search contract for the flight-fare-research skill (stdlib only, no network).

A contract is the user's answers written down before any search: a list of
legs with airport groups and dates, the travellers, cabins, bags and limits.
This module validates it, fills defaults, expands the legs into date tuples
and builds the comparison cells a run must finish. `run_log.py` stores it.
"""
from __future__ import annotations

import copy
import re
from datetime import date, timedelta

CABINS = ("economy", "premium", "business", "first")
HACKS = ("split", "open_jaw", "stopover")
SCOPES = ("quick", "full")
SPEEDS = ("fast", "thorough")
VIA = ("rail", "bus", "flight", "car")
DATE_KINDS = ("fixed", "range", "flex", "after_leg")
THOROUGH_TUPLE_CAP = 200
FAST_DEFAULT_ABOVE = 10  # more tuples than this and the default speed is fast
DEFAULT_HACKS = {"split": True, "open_jaw": True, "stopover": False}

RUN_ID = re.compile(r"^[a-z0-9][a-z0-9-]*$")
HHMMSS = re.compile(r"^\d\d:\d\d:\d\d$")
HHMM = re.compile(r"^\d\d:\d\d$")
IATA = re.compile(r"^[A-Z]{3}$")
AIRLINE = re.compile(r"^[A-Z0-9]{2}$")
GROUP_REF = re.compile(r"^(from|to):(\d+)$")
WINDOW_KEYS = ("dep_after", "dep_before", "arr_after", "arr_before")


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


def _is_date(value) -> bool:
    try:
        date.fromisoformat(value)
        return isinstance(value, str)
    except (TypeError, ValueError):
        return False


def _is_int(value, minimum=0) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= minimum


def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value == value


# --------------------------------------------------------------------------- groups

def airports(group: dict) -> list[str]:
    """The airport codes of a normalized group, home airport first."""
    return [a["code"] for a in group.get("airports") or []]


def home_airport(group: dict) -> str | None:
    codes = airports(group)
    return codes[0] if codes else None


def via_airports(contract: dict) -> dict[str, dict]:
    """Every airport reached by ground transport in a normalized contract, by code."""
    out = {}
    for lg in contract["legs"]:
        for side in ("from", "to"):
            for a in lg[side].get("airports") or []:
                if a.get("via"):
                    out.setdefault(a["code"], a)
    return out


def _group_errors(side_value, leg_no: int, side: str, n_legs: int) -> list[str]:
    where = f"leg {leg_no} {side}"
    if isinstance(side_value, str):
        match = GROUP_REF.match(side_value)
        if not match:
            return [f"{where}: {side_value!r} must be a group object or a reference such as to:1"]
        target = int(match.group(2))
        if target < 1 or target >= leg_no:
            return [f"{where}: reference {side_value} must point at an earlier leg (1..{leg_no - 1})"]
        return []
    if not isinstance(side_value, dict):
        return [f"{where}: must be a group object or a reference"]
    errors = []
    airports_in = side_value.get("airports")
    if not isinstance(airports_in, list):
        return [f"{where}: airports must be a list"]
    if not airports_in and not side_value.get("region"):
        errors.append(f"{where}: airports must not be empty (a region group may start empty)")
    for a in airports_in:
        if not isinstance(a, dict) or not isinstance(a.get("code"), str) or not IATA.match(a["code"]):
            errors.append(f"{where}: each airport needs a three-letter uppercase code, got {a!r}")
            continue
        if a.get("via") is not None and a["via"] not in VIA:
            errors.append(f"{where}: {a['code']} via must be one of {', '.join(VIA)}")
        if "overnight_ok" in a and not isinstance(a["overnight_ok"], bool):
            errors.append(f"{where}: {a['code']} overnight_ok must be true or false")
    return errors


def _resolve_group(contract: dict, side_value, default_overnight: bool) -> dict:
    """A normalized group dict, following a reference to another leg."""
    if isinstance(side_value, str):
        match = GROUP_REF.match(side_value)
        return _resolve_group(contract, contract["legs"][int(match.group(2)) - 1][match.group(1)], default_overnight)
    group = {"name": side_value.get("name") or "+".join(a["code"] for a in side_value.get("airports") or []),
             "region": bool(side_value.get("region")), "airports": []}
    for a in side_value.get("airports") or []:
        entry = {"code": a["code"], "via": a.get("via"), "overnight_ok": a.get("overnight_ok", default_overnight)}
        group["airports"].append(entry)
    return group


# --------------------------------------------------------------------------- dates

def _date_errors(dates, leg_no: int) -> list[str]:
    where = f"leg {leg_no} dates"
    if not isinstance(dates, dict):
        return [f"{where}: must be an object"]
    kinds = [k for k in DATE_KINDS if k in dates]
    if len(kinds) != 1:
        return [f"{where}: needs exactly one of {', '.join(DATE_KINDS)}"]
    kind, spec = kinds[0], dates[kinds[0]]
    if kind == "fixed":
        return [] if _is_date(spec) else [f"{where}: fixed must be a YYYY-MM-DD date"]
    if not isinstance(spec, dict):
        return [f"{where}: {kind} must be an object"]
    if kind == "range":
        if not (_is_date(spec.get("from")) and _is_date(spec.get("to"))):
            return [f"{where}: range needs from and to as YYYY-MM-DD dates"]
        if spec["from"] > spec["to"]:
            return [f"{where}: range from must not be after to"]
    elif kind == "flex":
        if not _is_date(spec.get("date")) or not _is_int(spec.get("minus")) or not _is_int(spec.get("plus")):
            return [f"{where}: flex needs date (YYYY-MM-DD), minus and plus (days >= 0)"]
    else:
        target = spec.get("leg")
        if not _is_int(target, 1) or target >= leg_no:
            return [f"{where}: after_leg.leg must name an earlier leg (1..{leg_no - 1})"]
        if not _is_int(spec.get("min_days")) or not _is_int(spec.get("max_days")) \
                or spec["min_days"] > spec["max_days"]:
            return [f"{where}: after_leg needs min_days <= max_days (days >= 0)"]
    return []


def _iso_range(first: str, last: str):
    day, end = date.fromisoformat(first), date.fromisoformat(last)
    while day <= end:
        yield day.isoformat()
        day += timedelta(days=1)


def _leg_dates(dates: dict, earlier: list[str]) -> list[str]:
    """Candidate dates for one leg given the dates chosen for earlier legs."""
    if "fixed" in dates:
        return [dates["fixed"]]
    if "range" in dates:
        return list(_iso_range(dates["range"]["from"], dates["range"]["to"]))
    if "flex" in dates:
        f = dates["flex"]
        anchor = date.fromisoformat(f["date"])
        return [(anchor + timedelta(days=d)).isoformat() for d in range(-f["minus"], f["plus"] + 1)]
    a = dates["after_leg"]
    base = date.fromisoformat(earlier[a["leg"] - 1])
    return [(base + timedelta(days=d)).isoformat() for d in range(a["min_days"], a["max_days"] + 1)]


def expand_tuples(contract: dict) -> list[list[str]]:
    """Every date tuple of a normalized contract: one date per leg, never going backwards."""
    legs = contract["legs"]

    def extend(chosen: list[str]) -> list[list[str]]:
        if len(chosen) == len(legs):
            return [chosen]
        out = []
        for day in _leg_dates(legs[len(chosen)]["dates"], chosen):
            if chosen and day < chosen[-1]:
                continue
            out.extend(extend(chosen + [day]))
        return out

    unique = {tuple(t) for t in extend([])}
    return sorted(list(t) for t in unique)


def _tuple_errors(contract: dict) -> list[str]:
    """Errors that need every leg's dates: impossible orderings and the thorough cap."""
    legs = contract["legs"]
    for i in range(1, len(legs)):
        earlier = legs[i - 1]["dates"]
        this = legs[i]["dates"]
        if "fixed" in this and "fixed" in earlier and this["fixed"] < earlier["fixed"]:
            return [f"leg {i + 1}: date {this['fixed']} is before leg {i} ({earlier['fixed']})"]
    count = len(expand_tuples(contract))
    if count == 0:
        return ["legs: no date tuple keeps the legs in order; widen a range or fix a date"]
    if contract.get("speed", _default_speed(count)) == "thorough" and count > THOROUGH_TUPLE_CAP:
        return [f"{count} date tuples exceed the thorough cap of {THOROUGH_TUPLE_CAP}; "
                "use speed fast or narrow the dates"]
    return []


def _default_speed(tuple_count: int) -> str:
    return "fast" if tuple_count > FAST_DEFAULT_ABOVE else "thorough"


# --------------------------------------------------------------------------- shape

def trip_shape(legs: list[dict]) -> str:
    """one_way, return (two legs that reverse each other) or multi_city."""
    if len(legs) == 1:
        return "one_way"
    if len(legs) == 2:
        a, b = legs
        if _same_side(a["from"], b["to"], legs, 0, "from") and _same_side(a["to"], b["from"], legs, 0, "to"):
            return "return"
    return "multi_city"


def _same_side(x, y, legs, leg_index, side) -> bool:
    """Whether two raw side values name the same group (by reference or by codes)."""
    def codes(v):
        if isinstance(v, str):
            m = GROUP_REF.match(v)
            if not m:
                return None
            return codes(legs[int(m.group(2)) - 1][m.group(1)])
        return tuple(a.get("code") for a in (v.get("airports") or []) if isinstance(a, dict)) + (v.get("name"),)
    return codes(x) == codes(y)


# --------------------------------------------------------------------------- validate

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
    if "speed" in contract and contract["speed"] not in SPEEDS:
        errors.append("speed must be fast or thorough")
    legs = contract.get("legs")
    if not isinstance(legs, list) or not legs or not all(isinstance(lg, dict) for lg in legs):
        errors.append("legs must be a non-empty list of leg objects")
        legs = []
    for n, lg in enumerate(legs, 1):
        for side in ("from", "to"):
            errors.extend(_group_errors(lg.get(side), n, side, len(legs)))
        errors.extend(_date_errors(lg.get("dates"), n))
    travelers = contract.get("travelers")
    adults = travelers.get("adults") if isinstance(travelers, dict) else None
    if not _is_int(adults, 1):
        errors.append("travelers.adults must be an integer >= 1")
    if isinstance(travelers, dict):
        ages = travelers.get("children_ages", [])
        if not isinstance(ages, list) or any(not _is_int(a) for a in ages):
            errors.append("travelers.children_ages must be a list of ages (integers)")
        if not _is_int(travelers.get("infants", 0)):
            errors.append("travelers.infants must be an integer >= 0")
    currency = contract.get("currency")
    if not isinstance(currency, str) or not IATA.match(currency):
        errors.append("currency is required: a three-letter code such as CHF")
    cabins = contract.get("cabins")
    if not isinstance(cabins, list) or not cabins:
        errors.append("cabins must be a non-empty list")
    elif any(c not in CABINS for c in cabins):
        errors.append(f"cabins must be drawn from {', '.join(CABINS)}")
    bags = contract.get("bags")
    checked = bags.get("checked_per_person") if isinstance(bags, dict) else None
    if not _is_int(checked):
        errors.append("bags.checked_per_person is required: an integer >= 0")
    if isinstance(bags, dict) and not _is_int(bags.get("cabin_per_person", 0)):
        errors.append("bags.cabin_per_person must be an integer >= 0 (full-size cabin bags per person)")
    cap = contract.get("max_duration")
    if cap is not None:
        try:
            duration_to_seconds(cap.get("value") if isinstance(cap, dict) else None)
        except ValueError:
            errors.append("max_duration.value must be HH:MM:SS (or max_duration null for no cap)")
        if isinstance(cap, dict) and not isinstance(cap.get("strict"), bool):
            errors.append("max_duration.strict must be true or false")
    if contract.get("max_stops") is not None and not _is_int(contract["max_stops"]):
        errors.append("max_stops must be null or an integer >= 0")
    errors.extend(_window_errors(contract.get("time_windows", []), len(legs)))
    airlines = contract.get("airlines", {"prefer": [], "exclude": []})
    if not isinstance(airlines, dict) or any(
            not isinstance(airlines.get(k, []), list) or any(not isinstance(x, str) or not AIRLINE.match(x)
                                                             for x in airlines.get(k, []))
            for k in ("prefer", "exclude")):
        errors.append("airlines must be {\"prefer\": [codes], \"exclude\": [codes]} with two-letter airline codes")
    hacks = contract.get("hacks", {})
    if not isinstance(hacks, dict) or any(k not in HACKS or not isinstance(v, bool) for k, v in hacks.items()):
        errors.append(f"hacks must be an object with true/false {', '.join(HACKS)}")
    if not isinstance(contract.get("self_transfer_ok", False), bool):
        errors.append("self_transfer_ok must be true or false")
    positioning = contract.get("positioning", {})
    if not isinstance(positioning, dict) or any(
            not isinstance(positioning.get(k, True), bool) for k in ("allowed", "overnight_ok")):
        errors.append("positioning must be an object with true/false allowed, overnight_ok")
    budget = contract.get("budget")
    if budget is not None and (not _is_number(budget) or budget < 0):
        errors.append("budget must be null or a non-negative number")
    if not _is_int(contract.get("shortlist", 4), 1):
        errors.append("shortlist must be an integer >= 1")
    if not errors:
        errors.extend(_scope_errors(contract))
        if not errors:
            errors.extend(_tuple_errors(normalize_contract(contract)))
    return errors


def _window_errors(windows, n_legs: int) -> list[str]:
    if not isinstance(windows, list):
        return ["time_windows must be a list"]
    errors = []
    for w in windows:
        if not isinstance(w, dict) or not _is_int(w.get("leg"), 1) or w["leg"] > n_legs:
            errors.append(f"time_windows: leg {w.get('leg') if isinstance(w, dict) else w!r} is not a leg of this trip")
            continue
        for k in WINDOW_KEYS:
            if k in w and (not isinstance(w[k], str) or not HHMM.match(w[k])):
                errors.append(f"time_windows: leg {w['leg']} {k} must be HH:MM")
        if not any(k in w for k in WINDOW_KEYS):
            errors.append(f"time_windows: leg {w['leg']} needs at least one of {', '.join(WINDOW_KEYS)}")
    return errors


def _scope_errors(contract: dict) -> list[str]:
    errors = []
    legs = contract["legs"]
    if contract["scope"] == "quick":
        if any("fixed" not in lg["dates"] for lg in legs):
            errors.append("a quick scope needs fixed dates on every leg; use scope full for flexible dates")
        if len(contract["cabins"]) > 1:
            errors.append("a quick scope compares one cabin; use scope full for several")
    empty_regions = [n for n, lg in enumerate(legs, 1) for side in ("from", "to")
                     if isinstance(lg[side], dict) and lg[side].get("region") and not lg[side].get("airports")]
    if empty_regions and contract.get("speed", "fast") != "fast":
        errors.append(f"leg {empty_regions[0]}: a region group without airports needs speed fast "
                      "(discovery proposes the shortlist)")
    return errors


# --------------------------------------------------------------------------- normalize

def normalize_contract(contract: dict) -> dict:
    """Return a copy of a valid contract with references resolved and defaults filled."""
    c = copy.deepcopy(contract)
    c.setdefault("assumptions", [])
    positioning = {"allowed": True, "overnight_ok": False}
    positioning.update(c.get("positioning") or {})
    c["positioning"] = positioning
    raw_legs = c["legs"]
    c["shape"] = trip_shape(raw_legs)
    legs = []
    for lg in raw_legs:
        legs.append({"from": _resolve_group(c, lg["from"], positioning["overnight_ok"]),
                     "to": _resolve_group(c, lg["to"], positioning["overnight_ok"]),
                     "dates": lg["dates"]})
    if not positioning["allowed"]:
        dropped = set()
        for lg in legs:
            for side in ("from", "to"):
                keep = [a for a in lg[side]["airports"] if not a.get("via")]
                dropped.update(a["code"] for a in lg[side]["airports"] if a.get("via"))
                lg[side]["airports"] = keep
        if dropped:
            c["assumptions"].append("positioning not allowed: dropped " + ", ".join(sorted(dropped)))
    c["legs"] = legs
    c.setdefault("max_duration", None)
    c.setdefault("max_stops", None)
    c.setdefault("time_windows", [])
    airlines = {"prefer": [], "exclude": []}
    airlines.update(c.get("airlines") or {})
    c["airlines"] = airlines
    hacks = dict(DEFAULT_HACKS)
    hacks.update(c.get("hacks") or {})
    if c["scope"] == "quick":
        hacks = {h: False for h in HACKS}
    c["hacks"] = hacks
    c.setdefault("self_transfer_ok", False)
    c.setdefault("budget", None)
    c.setdefault("shortlist", 4)
    c.setdefault("event", None)
    c["travelers"].setdefault("children_ages", [])
    c["travelers"].setdefault("infants", 0)
    c["bags"].setdefault("cabin_per_person", 0)
    if "speed" not in c:
        c["speed"] = _default_speed(len(expand_tuples(c)))
    return c


# --------------------------------------------------------------------------- cells

def region_groups(contract: dict) -> list[tuple[int, str]]:
    """(leg index, side) of every region group that still has no airports."""
    out, seen = [], set()
    for i, lg in enumerate(contract["legs"]):
        for side in ("from", "to"):
            g = lg[side]
            if g.get("region") and not g["airports"] and g["name"] not in seen:
                seen.add(g["name"])
                out.append((i, side))
    return out


def tuple_id(dates: list[str]) -> str:
    return "_".join(dates)


def _hack_auto(contract: dict, hack: str):
    if hack in ("split", "open_jaw") and contract["shape"] != "return":
        return {"as": "na", "reason": "one-way trip" if contract["shape"] == "one_way" else "multi-city trip"}
    if hack == "open_jaw":
        first = contract["legs"][0]
        if len(airports(first["from"])) < 2 and len(airports(first["to"])) < 2:
            return {"as": "na", "reason": "no other airport to open the jaw"}
    return None


def build_cells(contract: dict) -> list[dict]:
    """The comparisons a normalized run must finish, in report order."""
    c = contract
    first = c["legs"][0]
    origins, destinations = airports(first["from"]), airports(first["to"])
    cells = []
    for cabin in c["cabins"]:
        if c["speed"] == "thorough":
            for origin in origins:
                for dest in destinations:
                    for dates in expand_tuples(c):
                        cells.append({"id": f"{cabin}/baseline/{origin}-{dest}/{tuple_id(dates)}", "kind": "baseline",
                                      "cabin": cabin, "origin": origin, "destination": dest, "dates": dates,
                                      "auto": None})
        else:
            for dest in destinations:
                cells.append({"id": f"{cabin}/discover/{dest}", "kind": "discover", "cabin": cabin,
                              "destination": dest, "auto": None})
            for dest in destinations:
                cells.append({"id": f"{cabin}/confirm/{dest}", "kind": "confirm", "cabin": cabin,
                              "destination": dest, "tuples": [], "auto": None})
        for hack in HACKS:
            if c["hacks"].get(hack):
                cells.append({"id": f"{cabin}/hack/{hack}", "kind": "hack", "cabin": cabin, "hack": hack,
                              "auto": _hack_auto(c, hack)})
        cells.append({"id": f"{cabin}/crosscheck", "kind": "crosscheck", "cabin": cabin, "auto": None})
        cells.append({"id": f"{cabin}/reprice", "kind": "reprice", "cabin": cabin, "auto": None})
    return cells


def apply_shortlist(contract: dict, codes: list[str]) -> dict:
    """Add discovered gateway airports to every empty region group; rebuild tuples and cells."""
    c = copy.deepcopy(contract)
    bad = [code for code in codes if not isinstance(code, str) or not IATA.match(code)]
    if bad:
        raise ValueError(f"not three-letter uppercase airport codes: {', '.join(map(str, bad))}")
    present = {a for lg in c["legs"] for side in ("from", "to") for a in airports(lg[side])}
    dup = [code for code in codes if code in present]
    if dup:
        raise ValueError(f"already in the contract: {', '.join(dup)}")
    targets = region_groups(c)
    if not targets:
        raise ValueError("no region group is waiting for a shortlist")
    groups = [c["legs"][i][side] for i, side in targets]
    names = {g["name"] for g in groups}
    for lg in c["legs"]:
        for side in ("from", "to"):
            g = lg[side]
            if g.get("region") and g["name"] in names:
                g["airports"] = [{"code": code, "via": None, "overnight_ok": c["positioning"]["overnight_ok"]}
                                 for code in codes]
    c["date_tuples"] = expand_tuples(c)
    c["cells"] = build_cells(c)
    return c


def fill_confirm_cells(contract: dict, picks: dict[str, list[list[str]]]) -> dict:
    """Set the tuples to confirm on each `{cabin}/confirm/{DEST}` cell from picks[f"{cabin}/{DEST}"]."""
    c = copy.deepcopy(contract)
    by_id = {cell["id"]: cell for cell in c.get("cells") or []}
    for key, tuples in picks.items():
        cell = by_id.get(f"{key.split('/')[0]}/confirm/{key.split('/', 1)[1]}")
        if not cell:
            raise ValueError(f"no confirm cell for {key}")
        cell["tuples"] = [list(t) for t in tuples]
    return c
