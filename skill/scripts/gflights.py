#!/usr/bin/env python3
"""Google Flights helpers for the flight-fare-research skill (stdlib only).

  gflights.py url --cabin C [--adults N] [--children N] [--infants N] [--currency CHF] LEG [LEG ...]
      LEG = FROM[+FROM...]-TO[+TO...]@YYYY-MM-DD. One leg is a one-way search, two legs
      that reverse each other a round trip, anything else multi-city. Several airports
      on one end are searched together (all nearby airports in one search). Works for
      every cabin; the natural-language ?q= URL does not open premium or first.
  gflights.py parse --anchor YYYY-MM-DD [FILE|-]
      Page text (markdown or innerText) to JSON: state (results, empty, loading,
      challenge), the cabin the page has selected, the dates its "Track prices" line
      repeats, and one card per listed itinerary (the first leg only). --anchor is the
      date of the leg the list shows; it fixes the year of "Dec 22" style dates.
  gflights.py sweep --session ffr-google-N --run DIR [--cabins C,...] [--tuples D1_D2,...]
                    [--origin X] [--destination Y] [--top N] [--pause S] [--browser ID] [--attended]
      Drives a BrowserAct session you opened yourself (never the user's): one search per
      date tuple and cabin of a run_log.py run, waits for the first priced card instead of
      a fixed delay, checks that the page repeats the cabin and dates, and records the
      cheapest cards within the duration cap as list-fare rows (first leg only). On a
      challenge it follows the policy in browseract.py and stops when nothing clears it.
  gflights.py explore --region "Southeast Asia" --from ZRH --window 2027-02-01,2027-02-10
      The Explore page URL and the form steps for a region (Explore ignores query
      parameters for regions; the cards are read by hand, see references/discovery.md).

Every price here is a Google list fare: a lead until a seller's page qualifies it.
Exit codes: 0 ok, 2 usage error, 3 sweep stopped by a challenge.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import subprocess
import sys
import time
from datetime import date, datetime, timedelta, timezone

sys.dont_write_bytecode = True  # never leave __pycache__ inside the skill folder
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import browseract  # noqa: E402
import ffr_contract  # noqa: E402
import run_log  # noqa: E402
from ffr_contract import UsageError  # noqa: E402

CABIN_CODES = {"economy": 1, "premium": 2, "business": 3, "first": 4}
CABIN_ALIASES = {"premium economy": "premium", "premium_economy": "premium"}
CABIN_SHOWN = {"Economy": "economy", "Premium economy": "premium", "Business": "business", "First": "first"}
TRAVELLER = {"adult": 1, "child": 2, "infant_lap": 4}
LEG = re.compile(r"^([A-Z]{3}(?:\+[A-Z]{3})*)-([A-Z]{3}(?:\+[A-Z]{3})*)@(\d{4}-\d{2}-\d{2})$")

SECTION = re.compile(r"^(?:(?:top|other) )?(?:departing |returning )?flights(?: to .+)?$", re.I)
CHALLENGE = re.compile(r"unusual traffic|/sorry/|captcha|not a robot|are you a (?:robot|human)|access denied", re.I)
TIME = re.compile(r"(\d{1,2}):(\d{2}) ([AP]M) on \w{3}, (\w{3}) (\d{1,2})")
PRICE = re.compile(r"^\s+([A-Z]{3}) ([\d,'’]+)\s*$", re.M)
DURATION = re.compile(r"^\s+(?:(\d+) hr(?: (\d+) min)?|(\d+) min)\s*$", re.M)
STOPS = re.compile(r"^\s+(Nonstop|(\d+) stops?)\s*$", re.M)
FROM_TO = re.compile(r"^\s+([A-Z]{3})\n[^\n]*\n\s+–\n\s+([A-Z]{3})\s*$", re.M)
LAYOVER = re.compile(r"^\s+(?:\d+ hr(?: \d+ min)?|\d+ min) ([A-Z]{3})\s*$", re.M)
MIXED = re.compile(r"^\s+((?:Economy|Premium [Ee]conomy|Business|First)[^\n]*\+[^\n]*?)\s*$", re.M)
SELF_TRANSFER = re.compile(r"self[- ]transfer|separate tickets", re.I)
TRACK = re.compile(r"^Track prices from .* departing (\d{4}-\d{2}-\d{2})(?: and returning (\d{4}-\d{2}-\d{2}))?\s*$", re.M)
SELECTED = re.compile(r"^(Economy|Premium economy|Business|First)\n\* Economy\n\* Premium economy", re.M)
MONTHS = {m: n for n, m in enumerate("Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split(), 1)}


# --------------------------------------------------------------------------- url

def _varint(n: int) -> bytes:
    out = bytearray()
    while True:
        low, n = n & 0x7F, n >> 7
        out.append(low | (0x80 if n else 0))
        if not n:
            return bytes(out)


def _field(number: int, payload) -> bytes:
    """Protobuf field: an int is a varint, bytes are length-delimited."""
    if isinstance(payload, int):
        return _varint(number << 3) + _varint(payload)
    return _varint(number << 3 | 2) + _varint(len(payload)) + payload


def _airport(code: str) -> bytes:
    return _field(1, 1) + _field(2, code.encode())


def parse_leg(text: str) -> tuple[list[str], list[str], str]:
    match = LEG.match(text)
    if not match:
        raise ValueError(f"leg {text!r} must look like ZRH-GIG@2026-12-22 (several airports joined by +)")
    date.fromisoformat(match.group(3))
    return match.group(1).split("+"), match.group(2).split("+"), match.group(3)


def url(cabin: str, legs: list[str], adults: int = 1, children: int = 0, infants: int = 0,
        currency: str = "CHF", lang: str = "en") -> str:
    """Google Flights search URL (the tfs parameter) for exact legs and travellers."""
    cabin = CABIN_ALIASES.get(cabin, cabin)
    if cabin not in CABIN_CODES:
        raise ValueError(f"cabin must be one of {', '.join(CABIN_CODES)}")
    if not legs:
        raise ValueError("give at least one leg")
    if adults < 1 or children < 0 or infants < 0:
        raise ValueError("at least one adult; children and infants cannot be negative")
    if not re.fullmatch(r"[A-Z]{3}", currency):
        raise ValueError("currency must be a three-letter code such as CHF")
    parsed = [parse_leg(leg) for leg in legs]
    if len(parsed) == 1:
        trip = 2
    elif len(parsed) == 2 and parsed[0][0] == parsed[1][1] and parsed[0][1] == parsed[1][0]:
        trip = 1
    else:
        trip = 3
    message = b"".join(
        _field(3, _field(2, day.encode()) + b"".join(_field(13, _airport(a)) for a in src)
               + b"".join(_field(14, _airport(a)) for a in dst))
        for src, dst, day in parsed)
    people = [TRAVELLER["adult"]] * adults + [TRAVELLER["child"]] * children + [TRAVELLER["infant_lap"]] * infants
    message += b"".join(_field(8, p) for p in people) + _field(9, CABIN_CODES[cabin]) + _field(19, trip)
    tfs = base64.urlsafe_b64encode(message).decode().rstrip("=")
    return f"https://www.google.com/travel/flights/search?tfs={tfs}&curr={currency}&hl={lang}"


# --------------------------------------------------------------------------- parse

def _when(match, anchor: date) -> str:
    hour, minute, half, month, day = match
    hour = int(hour) % 12 + (12 if half == "PM" else 0)
    when = date(anchor.year, MONTHS[month], int(day))
    if when < anchor - timedelta(days=7):  # "Jan 13" after a December anchor
        when = date(anchor.year + 1, MONTHS[month], int(day))
    return f"{when.isoformat()}T{hour:02d}:{int(minute):02d}:00"


def _card(block: str, anchor: date, section: str):
    times = TIME.findall(block)
    price = PRICE.search(block)
    duration = DURATION.search(block)
    if len(times) < 2 or not price or not duration:
        return None
    hours = int(duration.group(1) or 0)
    minutes = int(duration.group(2) or duration.group(3) or 0)
    lines = [line.strip() for line in block.split("\n")]
    time_lines = [i for i, line in enumerate(lines) if TIME.search(line)]
    after = lines[time_lines[1] + 1] if time_lines[1] + 1 < len(lines) else ""
    airline_text = "" if DURATION.match("  " + after) else after
    airlines, _, operated = airline_text.partition("Operated by")
    stops = STOPS.search(block)
    ends = FROM_TO.search(block)
    mixed = MIXED.search(block)
    return {"price": float(re.sub(r"[,'’]", "", price.group(2))), "currency": price.group(1),
            "dep": _when(times[0], anchor), "arr": _when(times[1], anchor),
            "duration": f"{hours:02d}:{minutes:02d}:00",
            "stops": 0 if not stops or stops.group(1) == "Nonstop" else int(stops.group(2)),
            "airlines": airlines.strip(), "operated_by": operated.strip() or None,
            "from": ends.group(1) if ends else None, "to": ends.group(2) if ends else None,
            "layovers": LAYOVER.findall(block), "self_transfer": bool(SELF_TRANSFER.search(block)),
            "cabin_label": mixed.group(1) if mixed else None, "section": section}


def parse(text: str, anchor: str, explore: bool = False) -> dict:
    """Read one Google Flights results page. The cards keep the page's order; the duplicate
    rendering Google appends while it fetches more results is dropped.

    With explore=True the page is an Explore (region) page: no capture of its card text
    exists yet, so the state is `challenge` or `unavailable` and the cards are read by hand."""
    text = text.replace(" ", " ").replace(" ", " ")
    if explore:
        state = "challenge" if CHALLENGE.search(text[:5000]) else "unavailable"
        return {"state": state, "destinations": [],
                "note": "read the destination cards by hand and record discover rows (references/discovery.md)"}
    out = {"state": "loading", "cabin": None, "departing": None, "returning": None, "cards": []}
    if CHALLENGE.search(text[:5000]):
        out["state"] = "challenge"
        return out
    selected = SELECTED.search(text)
    out["cabin"] = CABIN_SHOWN[selected.group(1)] if selected else None
    track = TRACK.search(text)
    if track:
        out["departing"], out["returning"] = track.group(1), track.group(2)
    start, seen = date.fromisoformat(anchor), set()
    for chunk in re.split(r"^### ", text, flags=re.M)[1:]:
        title = chunk.split("\n", 1)[0].strip()
        if not SECTION.match(title):
            continue
        for block in re.split(r"^\* ", chunk, flags=re.M)[1:]:
            card = _card(block, start, title)
            key = card and (card["dep"], card["arr"], card["airlines"], card["price"])
            if card and key not in seen:
                seen.add(key)
                out["cards"].append(card)
    if out["cards"]:
        out["state"] = "results"
    elif "No results returned" in text:
        out["state"] = "empty"
    return out


# --------------------------------------------------------------------------- sweep

def _seconds(hhmmss: str) -> int:
    hours, minutes, seconds = (int(x) for x in hhmmss.split(":"))
    return hours * 3600 + minutes * 60 + seconds


def pick(cards: list[dict], cap: dict | None, top: int) -> list[dict]:
    """The cheapest `top` cards within the cap, plus the cheapest card overall when it breaks
    the cap and is cheaper (kept so the rejection is on record)."""
    ordered = sorted(cards, key=lambda c: c["price"])
    if not cap:
        return ordered[:top]
    limit = _seconds(cap["value"])
    within = [c for c in ordered if _seconds(c["duration"]) < limit
              or (not cap["strict"] and _seconds(c["duration"]) == limit)]
    chosen = within[:top] or ordered[:1]
    if ordered and within and ordered[0]["price"] < within[0]["price"]:
        chosen = [ordered[0]] + chosen
    return chosen


def _stamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def legs_for_tuple(contract: dict, dates: list[str], origin: str | None = None,
                   destination: str | None = None) -> list[str]:
    """Leg strings (FROM-TO@DATE) for one date tuple of a normalized contract.

    Each leg uses its group's home airport unless overridden: for a return trip `origin`
    and `destination` set both legs; for multi-city they set leg 1's ends only."""
    legs = contract["legs"]
    if len(dates) != len(legs):
        raise ValueError(f"tuple {dates} has {len(dates)} date(s) for {len(legs)} leg(s)")
    out = []
    for n, (lg, day) in enumerate(zip(legs, dates)):
        src = ffr_contract.home_airport(lg["from"])
        dst = ffr_contract.home_airport(lg["to"])
        if contract["shape"] == "return":
            src, dst = (origin or src, destination or dst) if n == 0 else (destination or src, origin or dst)
        elif n == 0:
            src, dst = origin or src, destination or dst
        out.append(f"{src}-{dst}@{day}")
    return out


def _parse_tuple(text: str) -> list[str]:
    return text.split("_")


def sweep(run_dir: str, session, *, cabins: list[str] | None = None, tuples: list[str] | None = None,
          origin: str | None = None, destination: str | None = None, top: int = 3, pause: float = 12,
          timeout: float = 45, poll: float = 1.5, sleep=time.sleep, engine: str = "browser-act",
          on_challenge=None, log=lambda message: None) -> dict:
    """One Google Flights search per cabin and date tuple of a run; rows saved as it goes.

    `session` is a browseract.Session (or anything with navigate() and read_markdown()).
    `on_challenge(session)` returns solved, assisted, user or blocked; blocked stops the sweep."""
    contract = run_log.load_run(run_dir)[0]
    cabins = cabins or contract["cabins"]
    origin = origin or ffr_contract.home_airport(contract["legs"][0]["from"])
    destination = destination or ffr_contract.home_airport(contract["legs"][0]["to"])
    home = origin.split("+")[0]  # several origins in one search: each card names its own airport
    wanted = contract.get("date_tuples") or ffr_contract.expand_tuples(contract)
    if tuples:
        keys = {tuple(_parse_tuple(t)) for t in tuples}
        wanted = [t for t in wanted if tuple(t) in keys]
    travellers = contract["travelers"]
    summary = {"searches": 0, "rows": 0, "challenges": 0, "stopped": None}
    for cabin in cabins:
        for dates in wanted:
            if summary["searches"]:
                sleep(pause)
            legs = legs_for_tuple(contract, dates, origin, destination)
            address = url(cabin, legs, adults=travellers["adults"], children=len(travellers["children_ages"]),
                          infants=travellers.get("infants", 0), currency=contract["currency"])
            session.navigate(address)
            summary["searches"] += 1
            result, waited, notes = parse(session.read_markdown(), dates[0]), 0.0, []
            while result["state"] == "loading" and waited < timeout:
                sleep(poll)
                waited += poll
                result = parse(session.read_markdown(), dates[0])
            base = {"source": "google-flights", "family": "google", "engine": engine, "url": address,
                    "retrieved_at": _stamp(), "cabin": cabin, "hack": None, "phase": "exact", "origin": home,
                    "destination": destination, "dates": list(dates)}
            label = f"{cabin} {'/'.join(dates)}"
            if result["state"] == "challenge":
                summary["challenges"] += 1
                outcome = on_challenge(session) if on_challenge else "blocked"
                if outcome != "blocked":
                    result = parse(session.read_markdown(), dates[0])
                    notes.append(f"challenge {outcome}")
                if result["state"] == "challenge" or outcome == "blocked":
                    _save(run_dir, [dict(base, outcome="blocked", notes="challenge page; sweep stopped")])
                    summary["stopped"] = "challenge"
                    log(f"{label}: CHALLENGE, stopped. Record it: source_ledger.py record google-flights blocked "
                        f"--engine {engine} --evidence \"challenge during sweep\"")
                    return summary
            problem = _mismatch(result, contract, cabin, dates, timeout)
            if result["state"] == "empty" and not problem:
                _save(run_dir, [dict(base, outcome="empty", notes="No results returned")])
                log(f"{label}: no results")
                continue
            if problem:
                _save(run_dir, [dict(base, outcome="error", notes=problem)])
                log(f"{label}: ERROR {problem}")
                continue
            rows = [_card_row(c, base, cabin, notes) for c in pick(result["cards"], contract.get("max_duration"), top)]
            saved = _save(run_dir, rows)
            summary["rows"] += len(saved)
            log(f"{label}: " + ", ".join(f"{i} {s} {r['tickets'][0]['price']:.0f}" for (i, s, _), r in zip(saved, rows)))
    return summary


def _mismatch(result: dict, contract: dict, cabin: str, dates: list[str], timeout: float) -> str | None:
    out_date = dates[0]
    ret_date = dates[1] if contract["shape"] == "return" else None
    if result["state"] == "loading":
        return f"no priced card within {timeout:.0f} s"
    if result["state"] == "empty":
        return None if result["departing"] in (None, out_date) else f"page repeats {result['departing']}"
    if result["cabin"] != cabin:
        return f"page shows cabin {result['cabin']}, not {cabin}"
    if contract["shape"] != "multi_city" and (result["departing"], result["returning"]) != (out_date, ret_date):
        return f"page repeats {result['departing']}/{result['returning']}, not {out_date}/{ret_date}"
    if any(c["dep"][:10] != out_date for c in result["cards"]):
        return f"cards depart on another day than {out_date}"
    return None


def _card_row(card: dict, base: dict, cabin: str, extra_notes: list[str] | None = None) -> dict:
    shown = {v: k for k, v in CABIN_SHOWN.items()}[cabin]
    notes = (f"Google list card ({card['section']}): first leg only, later legs not selected; "
             f"layovers {', '.join(card['layovers']) or '-'}")
    if card["operated_by"]:
        notes += f"; operated by {card['operated_by']}"
    for extra in extra_notes or []:
        notes += f"; {extra}"
    return dict(base, outcome="populated", cabin_label=card["cabin_label"] or shown,
                origin=card["from"] or base["origin"], currency=card["currency"], fx=None, price_basis="total",
                tickets=[{"price": card["price"], "quote_state": "list",
                          "provider": card["airlines"] or "Google Flights listing", "baggage": "unverified",
                          "bag_fee": None, "booking_url": base["url"]}],
                legs=[{"leg": 1, "part": 1, "from": card["from"] or base["origin"],
                       "to": card["to"] or base["destination"], "dep": card["dep"], "arr": card["arr"],
                       "duration": card["duration"], "stops": card["stops"],
                       "airlines": [card["airlines"]] if card["airlines"] else [],
                       "airport_change": False, "self_transfer": card["self_transfer"]}],
                components={}, notes=notes)


def _save(run_dir: str, rows: list[dict]):
    with run_log.locked(run_dir):
        return run_log.add_rows(run_dir, rows)


# --------------------------------------------------------------------------- explore

EXPLORE_BASE = "https://www.google.com/travel/explore"


def explore_url(region: str, origin: str, window: tuple[str, str], cabin: str = "economy",
                currency: str = "CHF", lang: str = "en") -> str:
    """The Explore page for a region search. Explore ignores query parameters for regions
    (2026-10-17: ?q= links land on an empty shell), so the form is driven by explore_steps()."""
    return f"{EXPLORE_BASE}?hl={lang}&curr={currency}"


def explore_steps(region: str, origin: str, window: tuple[str, str]) -> list[str]:
    """What to do on the Explore page, in order; read the destination cards by hand afterwards."""
    return [f"open {EXPLORE_BASE} and decline optional cookies",
            f"click the origin field (Where from?), type {origin}, pick the suggestion with the code {origin}",
            f"click the destination field (Where to?), type {region}, pick the region suggestion",
            f"open the dates control, choose Specific dates {window[0]} to {window[1]} "
            "(or Flexible dates for the month when the window spans it)",
            "wait for the destination cards with prices; a map plus a list of cities is the ready signal",
            "read each card: city, lowest price, dates, stops; record one discover row per gateway airport "
            "with run_log.py add (phase discover, quote_state list, baggage unverified)"]


# --------------------------------------------------------------------------- cli

def _read_text(path: str) -> str:
    if path == "-":
        return sys.stdin.read()
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("url", help="search URL for exact legs, any cabin")
    p.add_argument("--cabin", required=True)
    p.add_argument("--adults", type=int, default=1)
    p.add_argument("--children", type=int, default=0)
    p.add_argument("--infants", type=int, default=0, help="infants on lap")
    p.add_argument("--currency", default="CHF")
    p.add_argument("legs", nargs="+", metavar="LEG")
    p = sub.add_parser("parse", help="results page text to JSON cards")
    p.add_argument("--anchor", required=True, help="date of the leg the page lists (YYYY-MM-DD)")
    p.add_argument("--explore", action="store_true", help="the page is an Explore (region) page")
    p.add_argument("file", nargs="?", default="-")
    p = sub.add_parser("sweep", help="one search per date tuple and cabin of a run (BrowserAct)")
    p.add_argument("--run", help="run directory (default: most recent run)")
    p.add_argument("--cabins", help="comma-separated (default: the contract's cabins)")
    p.add_argument("--tuples", help="comma-separated date tuples, e.g. 2026-12-22_2027-01-12 (default: all)")
    p.add_argument("--origin")
    p.add_argument("--destination")
    p.add_argument("--top", type=int, default=3, help="cards recorded per search (default 3)")
    p.add_argument("--pause", type=float, default=12, help="seconds between searches (default 12)")
    p.add_argument("--session", required=True,
                   help="your own BrowserAct session, named ffr-google-N (opened with browseract.py / "
                        "browser-act --session NAME browser open <id> <url>); never the user's")
    p.add_argument("--browser", help="BrowserAct browser id or name the session runs in (default ffr)")
    p.add_argument("--attended", action="store_true", help="a human can clear a challenge via remote-assist")
    p = sub.add_parser("explore", help="Explore page URL and form steps for a region")
    p.add_argument("--region", required=True)
    p.add_argument("--from", dest="origin", required=True)
    p.add_argument("--window", required=True, help="first,last outbound dates, e.g. 2027-02-01,2027-02-10")
    p.add_argument("--cabin", default="economy")
    p.add_argument("--currency", default="CHF")
    args = parser.parse_args(argv)
    try:
        if args.cmd == "url":
            print(url(args.cabin, args.legs, args.adults, args.children, args.infants, args.currency))
        elif args.cmd == "parse":
            print(json.dumps(parse(_read_text(args.file), args.anchor, explore=args.explore), indent=2,
                             ensure_ascii=False))
        elif args.cmd == "explore":
            window = tuple(args.window.split(","))
            if len(window) != 2:
                raise ValueError("--window takes two dates separated by a comma")
            print(explore_url(args.region, args.origin, window, args.cabin, args.currency))
            for n, step in enumerate(explore_steps(args.region, args.origin, window), 1):
                print(f"{n}. {step}")
        else:
            session = browseract.Session(args.session, args.browser)
            run_dir = run_log.resolve_run_dir(args.run)
            state = browseract.status()
            if not args.browser:
                session.browser = browseract.default_browser(state["engine"])

            def on_challenge(current):
                return browseract.handle_challenge(current, logged_in=state["logged_in"],
                                                   user_reachable=args.attended, engine=state["engine"])

            summary = sweep(run_dir, session, cabins=args.cabins.split(",") if args.cabins else None,
                            tuples=args.tuples.split(",") if args.tuples else None, origin=args.origin,
                            destination=args.destination, top=args.top, pause=args.pause,
                            engine=state["engine"], on_challenge=on_challenge,
                            log=lambda message: print(message, flush=True))
            print(json.dumps(summary))
            return 3 if summary["stopped"] else 0
    except (ValueError, OSError, UsageError, subprocess.SubprocessError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
