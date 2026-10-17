#!/usr/bin/env python3
"""FlightList (flightlist.io) helpers for the flight-fare-research skill (stdlib only).

One FlightList search with a departure range and a return range lists the
cheapest itineraries across every date tuple in it, with both directions. This
script turns those cards into rows, and drives the whole search unattended
through a BrowserAct session you opened yourself.

  flightlist.py rows --run DIR [--top N] [--cabin C] [--hack H] [--engine E] [--phase P] FILE|-
      FILE is the JSON the extraction snippet in references/flightlist-browser.md
      returns (one object per li.flight: price, text, book). Prints a JSON array of
      rows for `run_log.py add --row -`: per date tuple of the run, the N cheapest
      cards within the duration cap, plus the cheapest card overall when it breaks
      the cap and is cheaper (kept so the rejection is on record). Tuples with no
      card are listed on stderr: search them separately or confirm them on Google.
  flightlist.py sweep --session ffr-flightlist-N --run DIR --cabin C --from ZRH[+BSL] --to GIG
                      [--top N] [--limit 200] [--attended]
      One range search per origin airport: types the airports with real keys, sets
      both date pickers from the contract, the form settings, submits, waits for the
      cards, extracts them and records discover rows as it goes.
  flightlist.py parse FILE|-
      The cards as JSON (both directions, segment flight numbers).

Every row is a list fare with baggage unverified, whatever the bag filter said:
qualify it on the Kiwi fare page (kiwi.py) or the airline. Exit 0 ok, 2 usage
error, 3 sweep stopped by a challenge.
"""
from __future__ import annotations

import argparse
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

MONTHS = {m: n for n, m in enumerate("Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split(), 1)}
PRICE = re.compile(r"^([A-Z]{3})\s?([\d,.']+)")
CLOCK = r"(\d{1,2}:\d{2}(?:[ap]m)?)"
SUMMARY = re.compile(CLOCK + r" - " + CLOCK + r" \w{3} (\w{3}) (\d{1,2})(?:st|nd|rd|th) (\d{4}) "
                     r"(\d+)h (\d+)m [^(]+\(([A-Z]{3})\) → [^(]+\(([A-Z]{3})\) (Direct|Nonstop|(\d+) Stops?)")
SEGMENT = re.compile(r"\w{3} (\w{3}) (\d{1,2})(?:st|nd|rd|th) (\d{4}) ([^·()]+?) · ([A-Z0-9]{2} ?\d+) "
                     r"Depart at " + CLOCK + r" from [^(]+\(([A-Z]{3})\) Fly for (\d+)h (\d+)m "
                     r"Arrive at " + CLOCK + r" in [^(]+\(([A-Z]{3})\)")
HOME = "https://www.flightlist.io/"
CABIN_CODES = {"economy": "M", "premium": "W", "business": "C", "first": "F"}

EXTRACT_JS = """JSON.stringify([...document.querySelectorAll('li.flight')].map(c => ({
  price: c.querySelector('.price')?.textContent.trim(),
  text: c.textContent.replace(/\\s+/g, ' ').trim(),
  book: ([...c.querySelectorAll('a')].find(a => a.href.includes('kiwi.com')) || {}).href || null })))"""


# --------------------------------------------------------------------------- parsing

def _clock(text: str) -> tuple[int, int]:
    if text.endswith(("am", "pm")):
        hours, minutes = text[:-2].split(":")
        return int(hours) % 12 + (12 if text.endswith("pm") else 0), int(minutes)
    hours, minutes = text.split(":")
    return int(hours), int(minutes)


def _stamp(day: date, clock: tuple[int, int]) -> str:
    return f"{day.isoformat()}T{clock[0]:02d}:{clock[1]:02d}:00"


def _amount(text: str) -> float:
    cleaned = re.sub(r"[,'’]", "", text)
    return float(cleaned)


def parse_card(card) -> dict:
    """One card (the snippet's object, or its text) to price and two directions."""
    text = card["text"] if isinstance(card, dict) else card
    text = re.sub(r"\s+", " ", text).strip()
    price = PRICE.match(text)
    if not price:
        raise ValueError(f"card without a price: {text[:80]!r}")
    summaries = SUMMARY.findall(text)
    stay = text.find("Stay in ")
    segments = [(m.start(), m.groups()) for m in SEGMENT.finditer(text)]
    if not summaries or not segments:
        raise ValueError(f"card without a direction summary: {text[:80]!r}")
    if len(summaries) >= 2 and stay >= 0:
        plan = (("out", summaries[0], [g for at, g in segments if at < stay]),
                ("ret", summaries[1], [g for at, g in segments if at > stay]))
    elif len(summaries) == 1 and stay < 0:
        plan = (("out", summaries[0], [g for at, g in segments]),)
    else:
        raise ValueError(f"card mixes one-way and return text: {text[:80]!r}")
    directions = []
    for name, summary, part in plan:
        if not part:
            raise ValueError(f"no {name} segments in card: {text[:80]!r}")
        first, last = part[0], part[-1]
        dep_day = date(int(first[2]), MONTHS[first[0]], int(first[1]))
        last_day = date(int(last[2]), MONTHS[last[0]], int(last[1]))
        dep_clock, arr_clock = _clock(last[5]), _clock(last[9])
        arr_day = last_day + timedelta(days=1 if arr_clock < dep_clock else 0)
        airlines = list(dict.fromkeys(seg[3].strip() for seg in part))
        directions.append({
            "dir": name, "from": summary[7], "to": summary[8],
            "dep": _stamp(dep_day, _clock(first[5])), "arr": _stamp(arr_day, arr_clock),
            "duration": f"{int(summary[5]):02d}:{int(summary[6]):02d}:00",
            "stops": 0 if summary[9] in ("Direct", "Nonstop") else int(summary[10]),
            "airlines": airlines, "flights": [seg[4] for seg in part],
            "airport_change": any(a[10] != b[6] for a, b in zip(part, part[1:])),
            "mixed_carriers": len(airlines) > 1})
    return {"price": _amount(price.group(2)), "currency": price.group(1),
            "book": card.get("book") if isinstance(card, dict) else None, "directions": directions}


# --------------------------------------------------------------------------- rows

def _seconds(hhmmss: str) -> int:
    hours, minutes, seconds = (int(x) for x in hhmmss.split(":"))
    return hours * 3600 + minutes * 60 + seconds


def _within(card: dict, cap: dict | None) -> bool:
    if not cap:
        return True
    limit = _seconds(cap["value"])
    return all(_seconds(d["duration"]) < limit or (not cap["strict"] and _seconds(d["duration"]) == limit)
               for d in card["directions"])


def _row(card: dict, base: dict) -> dict:
    out = card["directions"][0]
    notes = ["FlightList card; flights " + " / ".join(" ".join(d["flights"]) for d in card["directions"]),
             "bag filter does not prove the bag is in the price"]
    for d in card["directions"]:
        if d["mixed_carriers"]:
            notes.append(f"{d['dir']}: {', '.join(d['airlines'])} (Kiwi combination: possible self-transfer, "
                         "confirm on the Kiwi page)")
    keys = ("from", "to", "dep", "arr", "duration", "stops", "airlines", "airport_change")
    legs = [dict({k: d[k] for k in keys}, leg=n, part=1, self_transfer=False)
            for n, d in enumerate(card["directions"], 1)]
    return dict(base, outcome="populated", origin=out["from"], destination=out["to"],
                dates=[d["dep"][:10] for d in card["directions"]], currency=card["currency"], fx=None,
                price_basis="total",
                tickets=[{"price": card["price"], "quote_state": "list", "provider": "Kiwi.com (via FlightList)",
                          "baggage": "unverified", "bag_fee": None, "booking_url": card["book"] or base["url"]}],
                legs=legs, components={}, notes="; ".join(notes))


def rows_for(contract: dict, raw_cards: list, *, top: int = 1, cabin: str | None = None, hack: str | None = None,
             engine: str = "browser", phase: str = "discover",
             retrieved_at: str | None = None) -> tuple[list[dict], list[str]]:
    """Rows per date tuple of the contract, and the tuples no card covered."""
    cap = contract.get("max_duration")
    cabin = cabin or contract["cabins"][0]
    base = {"source": "flightlist", "family": "kiwi", "engine": engine, "url": HOME,
            "retrieved_at": retrieved_at or datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "cabin": cabin, "cabin_label": cabin.capitalize(), "hack": hack, "phase": phase}
    parsed = sorted((parse_card(c) for c in raw_cards), key=lambda c: c["price"])
    by_tuple: dict[tuple, list] = {}
    for card in parsed:
        key = tuple(d["dep"][:10] for d in card["directions"])
        by_tuple.setdefault(key, []).append(card)
    rows, missing = [], []
    for dates in contract.get("date_tuples") or ffr_contract.expand_tuples(contract):
        found = by_tuple.get(tuple(dates), []) if len(dates) <= 2 else []
        if not found:
            missing.append(ffr_contract.tuple_id(dates))
            continue
        within = [c for c in found if _within(c, cap)]
        chosen = within[:top]
        if not within or found[0]["price"] < within[0]["price"]:
            chosen = [found[0]] + chosen
        rows.extend(_row(c, base) for c in chosen)
    return rows, missing


# --------------------------------------------------------------------------- sweep

def _js_date(day: str) -> str:
    d = date.fromisoformat(day)
    return f"new Date({d.year}, {d.month - 1}, {d.day})"


def _window(contract: dict) -> tuple[str, str, str, str]:
    tuples = contract.get("date_tuples") or ffr_contract.expand_tuples(contract)
    outs = [t[0] for t in tuples]
    rets = [t[1] for t in tuples if len(t) > 1] or outs
    return min(outs), max(outs), min(rets), max(rets)


def _pick_airport_js(code: str) -> str:
    return (f"(() => {{ const item = [...document.querySelectorAll('.eac-item')]"
            f".find(e => e.textContent.includes('({code})')); if (!item) return 'missing'; item.click(); return 'ok'; }})()")


def _settings_js(contract: dict, cabin: str, limit: int) -> str:
    bags = min(contract["bags"]["checked_per_person"], 2)
    stops = contract.get("max_stops")
    connections = "true" if contract.get("self_transfer_ok") else "false"
    sets = [("#type", "'return'" if contract["shape"] == "return" else "'oneway'"),
            ("#class", f"'{CABIN_CODES.get(cabin, 'M')}'"), ("#currency", f"'{contract['currency']}'"),
            ("#checkedbags", f"'{bags}'"), ("#sort", "'price'"), ("#limit", f"'{limit}'"),
            ("#connections", f"'{connections}'")]
    if stops is not None:
        sets.append(("#stops", f"'{stops}'"))
    body = " ".join(f"set('{sel}', {val});" for sel, val in sets)
    return ("(() => { const set = (sel, val) => { const el = document.querySelector(sel); if (el) { el.value = val; "
            "el.dispatchEvent(new Event('change', {bubbles: true})); } }; " + body + " return 'ok'; })()")


def sweep(run_dir: str, session, *, cabin: str | None = None, origins: list[str] | None = None,
          destination: str | None = None, top: int = 1, limit: int = 200, pause: float = 10,
          timeout: float = 60, poll: float = 2, sleep=time.sleep, engine: str = "browser-act",
          on_challenge=None, log=lambda message: None) -> dict:
    """One FlightList range search per origin airport, recorded as discover rows.

    `session` is a browseract.Session (navigate, run, eval, read_markdown)."""
    contract = run_log.load_run(run_dir)[0]
    if contract.get("shape") == "multi_city":
        raise UsageError("FlightList range searches cover one-way and return trips only; "
                         "for multi-city search leg 1 on Google (gflights.py url) or by hand")
    cabin = cabin or contract["cabins"][0]
    origins = origins or ffr_contract.airports(contract["legs"][0]["from"])
    destination = destination or ffr_contract.home_airport(contract["legs"][0]["to"])
    out_from, out_to, ret_from, ret_to = _window(contract)
    summary = {"searches": 0, "rows": 0, "missing": [], "challenges": 0, "stopped": None}
    for origin in origins:
        if summary["searches"]:
            sleep(pause)
        session.navigate(HOME)
        summary["searches"] += 1
        base = {"source": "flightlist", "family": "kiwi", "engine": engine, "url": HOME,
                "retrieved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "cabin": cabin,
                "hack": None, "phase": "discover", "origin": origin, "destination": destination}
        if browseract.is_challenge(session.read_markdown(), []):
            summary["challenges"] += 1
            outcome = on_challenge(session) if on_challenge else "blocked"
            if outcome == "blocked" or browseract.is_challenge(session.read_markdown(), []):
                _save(run_dir, [dict(base, outcome="blocked", notes="challenge page; sweep stopped")])
                summary["stopped"] = "challenge"
                log(f"{origin}-{destination}: CHALLENGE, stopped")
                return summary
        problem = _fill_form(session, contract, cabin, origin, destination, (out_from, out_to, ret_from, ret_to), limit)
        if problem:
            _save(run_dir, [dict(base, outcome="error", notes=problem)])
            log(f"{origin}-{destination}: ERROR {problem}")
            continue
        session.eval("document.querySelector('#submit').click()")
        waited, count = 0.0, 0
        while waited < timeout:
            count = int(re.sub(r"\D", "", session.eval("document.querySelectorAll('li.flight').length") or "0") or 0)
            if count:
                break
            sleep(poll)
            waited += poll
        if not count:
            _save(run_dir, [dict(base, outcome="empty", notes=f"no li.flight cards within {timeout:.0f} s")])
            log(f"{origin}-{destination}: no cards")
            continue
        try:
            cards = json.loads(session.eval(EXTRACT_JS))
        except ValueError as exc:
            _save(run_dir, [dict(base, outcome="error", notes=f"card extraction failed: {exc}")])
            continue
        rows, missing = rows_for(contract, cards, top=top, cabin=cabin, engine=engine, phase="discover")
        rows = [dict(r, origin=origin) if r["origin"] == origin else r for r in rows]
        saved = _save(run_dir, rows) if rows else []
        summary["rows"] += len(saved)
        summary["missing"] = missing
        log(f"{origin}-{destination}: {len(saved)} rows, {len(missing)} tuple(s) without a card")
    return summary


def _fill_form(session, contract: dict, cabin: str, origin: str, destination: str, window, limit: int) -> str | None:
    """Airports with real keys, both pickers, settings; a reason when a field did not commit."""
    for selector, code, data in (("#from", origin, "#from-data"), ("#to", destination, "#to-data")):
        session.run("input", "--selector", selector, "--text", code)
        session.eval(_pick_airport_js(code))
        got = session.eval(f"document.querySelector('{data}').value").strip().strip("'\"")
        if got != f"airport:{code}":
            return f"{selector} did not resolve to airport:{code} (got {got!r})"
    out_from, out_to, ret_from, ret_to = window
    session.eval(f"(() => {{ const dp = jQuery('#deprange').data('daterangepicker'); dp.setStartDate({_js_date(out_from)}); "
                 f"dp.setEndDate({_js_date(out_to)}); dp.container.find('.applyBtn').click(); return 'ok'; }})()")
    if contract["shape"] == "return":
        session.eval(f"(() => {{ const dp = jQuery('#retrange').data('daterangepicker'); dp.setStartDate({_js_date(ret_from)}); "
                     f"dp.setEndDate({_js_date(ret_to)}); dp.container.find('.applyBtn').click(); return 'ok'; }})()")
    got = session.eval("(() => { const f = s => jQuery(s).data('daterangepicker'); const d = f('#deprange'), r = f('#retrange'); "
                       "const iso = x => x ? x.format('YYYY-MM-DD') : ''; return [iso(d.startDate), iso(d.endDate), "
                       "iso(r && r.startDate), iso(r && r.endDate)].join('|'); })()").strip().strip("'\"")
    parts = got.split("|")
    if parts[:2] != [out_from, out_to] or (contract["shape"] == "return" and parts[2:4] != [ret_from, ret_to]):
        return f"date pickers read back {got!r}, not {out_from}..{out_to} / {ret_from}..{ret_to}"
    session.eval(_settings_js(contract, cabin, limit))
    return None


def _save(run_dir: str, rows: list[dict]):
    with run_log.locked(run_dir):
        return run_log.add_rows(run_dir, rows)


# --------------------------------------------------------------------------- cli

def _load(path: str):
    try:
        text = sys.stdin.read() if path == "-" else open(path, encoding="utf-8").read()
        data = json.loads(text)
    except (OSError, ValueError) as exc:
        raise UsageError(f"cannot read cards from {path}: {exc}")
    if not isinstance(data, list):
        raise UsageError("cards must be a JSON array")
    return data


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("rows", help="cards to run_log rows (JSON array on stdout)")
    p.add_argument("--run", help="run directory (default: most recent run)")
    p.add_argument("--top", type=int, default=1, help="cards within the cap kept per date tuple (default 1)")
    p.add_argument("--cabin", help="cabin searched (default: the contract's first cabin)")
    p.add_argument("--hack", help="hack these rows belong to, e.g. split")
    p.add_argument("--engine", default="browser", help="browser engine used, as in source_ledger.py")
    p.add_argument("--phase", default="discover", choices=("discover", "exact"))
    p.add_argument("file")
    p = sub.add_parser("parse", help="cards to JSON")
    p.add_argument("file")
    p = sub.add_parser("sweep", help="one range search per origin airport through a BrowserAct session")
    p.add_argument("--session", required=True, help="your own BrowserAct session, named ffr-flightlist-N")
    p.add_argument("--run", help="run directory (default: most recent run)")
    p.add_argument("--cabin", required=True)
    p.add_argument("--from", dest="origins", required=True, help="origin airports joined by +, e.g. ZRH+BSL")
    p.add_argument("--to", dest="destination", required=True)
    p.add_argument("--top", type=int, default=1)
    p.add_argument("--limit", type=int, default=200)
    p.add_argument("--browser", help="BrowserAct browser id or name (default ffr)")
    p.add_argument("--attended", action="store_true", help="a human can clear a challenge via remote-assist")
    args = parser.parse_args(argv)
    try:
        if args.cmd == "sweep":
            session = browseract.Session(args.session, args.browser)
            run_dir = run_log.resolve_run_dir(args.run)
            state = browseract.status()
            if not args.browser:
                session.browser = browseract.default_browser(state["engine"])

            def on_challenge(current):
                return browseract.handle_challenge(current, logged_in=state["logged_in"],
                                                   user_reachable=args.attended, engine=state["engine"])

            summary = sweep(run_dir, session, cabin=args.cabin, origins=args.origins.split("+"),
                            destination=args.destination, top=args.top, limit=args.limit, engine=state["engine"],
                            on_challenge=on_challenge, log=lambda message: print(message, flush=True))
            print(json.dumps(summary))
            return 3 if summary["stopped"] else 0
        cards = _load(args.file)
        if args.cmd == "parse":
            print(json.dumps([parse_card(c) for c in cards], indent=2, ensure_ascii=False))
            return 0
        contract = run_log.load_run(run_log.resolve_run_dir(args.run))[0]
        rows, missing = rows_for(contract, cards, top=args.top, cabin=args.cabin, hack=args.hack,
                                 engine=args.engine, phase=args.phase)
        print(json.dumps(rows, ensure_ascii=False))
        covered = len(contract.get("date_tuples") or ffr_contract.expand_tuples(contract)) - len(missing)
        print(f"{len(rows)} rows for {covered} date tuple(s)", file=sys.stderr)
        for t in missing:
            print(f"no card for {t}: search it separately", file=sys.stderr)
    except (ValueError, OSError, UsageError, subprocess.SubprocessError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
