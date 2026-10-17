#!/usr/bin/env python3
"""Kiwi.com fare-selection page helpers for the flight-fare-research skill (stdlib only).

A FlightList card's `Book Flight` link opens kiwi.com/en/booking/fare-selection/…,
which lists the airline's fare families with what each includes and the total
with Kiwi's fees, before any passenger detail. That page is a completed quote.

  kiwi.py fare --session ffr-kiwi-N --run DIR --supersedes rN URL [--browser ID] [--attended]
      Opens the fare page in a BrowserAct session you opened yourself, reads the
      families, picks the cheapest one that includes the requested checked bags
      (else the cheapest), and records a completed row that supersedes the list row.
  kiwi.py parse FILE|-
      The families on a saved page text, as JSON.

Stop before passenger details: never continue past the fare page. Exit 0 ok,
2 usage error, 3 stopped by a challenge.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone

sys.dont_write_bytecode = True  # never leave __pycache__ inside the skill folder
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import browseract  # noqa: E402
import run_log  # noqa: E402
from ffr_contract import UsageError  # noqa: E402

PRICE = re.compile(r"\b([A-Z]{3}) ?([\d]{1,3}(?:[,'’ ]\d{3})*(?:\.\d{2})?|\d+(?:\.\d{2})?)\b")
HEADING = re.compile(r"^#{1,6}\s*([^\n#]{2,40}?)\s*$", re.M)
FAMILY_LINE = re.compile(r"^((?:Economy |Business |Premium )?(?:Light|Basic|Standard|Classic|Flex|Plus|Comfort|Saver|"
                         r"Value|Smart|Premium|Flexible|Max))\s*$", re.M)
NO_CHECKED = re.compile(r"no checked (?:bag|baggage)|checked (?:bag|baggage)[^\n]*(?:not included|: none|: 0)|0 ?× ?\d+ ?kg checked",
                        re.I)
CHECKED = re.compile(r"checked (?:bag|baggage)[^\n]*?(\d+) ?× ?(\d+) ?kg|(\d+) ?× ?(\d+) ?kg checked|checked bag(?:gage)? included",
                     re.I)
CABIN = re.compile(r"cabin (?:bag|baggage)|carry-on", re.I)
STOP_WORDS = ("choose your fare", "select", "total", "changes", "passenger", "continue", "prices include")


def _amount(text: str) -> float:
    return float(re.sub(r"[,'’ ]", "", text))


def parse_fares(text: str) -> list[dict]:
    """The fare families on a fare-selection page: name, price, currency, bag states."""
    if browseract.CHALLENGE.search(text[:5000]):
        return []
    text = text.replace(" ", " ")
    heads = [(m.start(), m.end(), m.group(1).strip()) for m in HEADING.finditer(text)
             if m.group(1).strip().lower() not in STOP_WORDS and "fare" not in m.group(1).lower()]
    if not heads:
        heads = [(m.start(), m.end(), m.group(1).strip()) for m in FAMILY_LINE.finditer(text)]
    fares = []
    for n, (start, end, name) in enumerate(heads):
        block = text[end:heads[n + 1][0] if n + 1 < len(heads) else len(text)]
        price = PRICE.search(block)
        if not price or "select" not in block.lower():
            continue
        checked = bool(CHECKED.search(block)) and not NO_CHECKED.search(block)
        fares.append({"family": name, "price": _amount(price.group(2)), "currency": price.group(1),
                      "checked_bag": checked, "cabin_bag": bool(CABIN.search(block))})
    return fares


def pick_family(fares: list[dict], checked_per_person: int) -> dict | None:
    """The cheapest family that includes a checked bag when bags are requested, else the cheapest."""
    candidates = [f for f in fares if f["checked_bag"]] if checked_per_person > 0 else list(fares)
    return min(candidates, key=lambda f: f["price"]) if candidates else None


def completed_row(list_row: dict, fare: dict, url: str, engine: str) -> dict:
    """A completed Kiwi row for the same itinerary, superseding the list row."""
    keep = ("cabin", "cabin_label", "hack", "origin", "destination", "dates", "legs", "price_basis", "components")
    row = {k: list_row.get(k) for k in keep if k in list_row}
    row.update({"source": "kiwi", "family": "kiwi", "engine": engine, "outcome": "populated", "url": url,
                "retrieved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "phase": "exact",
                "currency": fare["currency"], "fx": None, "supersedes": list_row.get("id"),
                "tickets": [{"price": fare["price"], "quote_state": "completed", "provider": "Kiwi.com",
                             "baggage": "included" if fare["checked_bag"] else "fee_required", "bag_fee": None,
                             "cabin_bag": "included" if fare["cabin_bag"] else "unverified",
                             "booking_url": url}],
                "notes": f"Kiwi fare page: {fare['family']} family, total with Kiwi fees, before passenger details"})
    row.setdefault("components", {})
    row.setdefault("price_basis", "total")
    return row


def fare(run_dir: str, session, supersedes: str, url: str, *, engine: str = "browser-act", timeout: float = 45,
         on_challenge=None, sleep=None) -> tuple[str, str, list[str]] | None:
    """Open the fare page, pick the family, record the completed row. None when a challenge stopped it."""
    contract, records = run_log.load_run(run_dir)
    by_id = {r["id"]: r for r in records if r.get("type") == "row"}
    if supersedes not in by_id:
        raise UsageError(f"{supersedes} is not a row of this run (see run_log.py rank)")
    session.navigate(url)
    kwargs = {"timeout": timeout}
    if sleep:
        kwargs["sleep"] = sleep
    text = session.wait_for(r"[A-Z]{3} ?[\d,'’ ]+\.\d{2}", **kwargs) or session.read_markdown()
    if browseract.is_challenge(text, []):
        outcome = on_challenge(session) if on_challenge else "blocked"
        text = session.read_markdown() if outcome != "blocked" else text
        if browseract.is_challenge(text, []):
            with run_log.locked(run_dir):
                run_log.add_rows(run_dir, [{"source": "kiwi", "family": "kiwi", "engine": engine, "outcome": "blocked",
                                            "url": url, "retrieved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                                            "cabin": by_id[supersedes].get("cabin"), "notes": "challenge on the fare page"}])
            return None
    fares = parse_fares(text)
    chosen = pick_family(fares, contract["bags"]["checked_per_person"])
    if not chosen:
        raise UsageError("no fare family with a price found on the page" +
                         (" that includes a checked bag" if fares else "") + "; read it by hand")
    row = completed_row(by_id[supersedes], chosen, url, engine)
    with run_log.locked(run_dir):
        return run_log.add_rows(run_dir, [row])[0]


def _read_text(path: str) -> str:
    return sys.stdin.read() if path == "-" else open(path, encoding="utf-8").read()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("fare", help="record the fare page as a completed row")
    p.add_argument("--session", required=True, help="your own BrowserAct session, named ffr-kiwi-N")
    p.add_argument("--run", help="run directory (default: most recent run)")
    p.add_argument("--supersedes", required=True, help="the list row this quote replaces, e.g. r4")
    p.add_argument("url", help="the kiwi.com fare-selection URL from the FlightList card")
    p.add_argument("--browser", help="BrowserAct browser id or name (default ffr)")
    p.add_argument("--attended", action="store_true", help="a human can clear a challenge via remote-assist")
    p = sub.add_parser("parse", help="fare families on a saved page text")
    p.add_argument("file", nargs="?", default="-")
    args = parser.parse_args(argv)
    try:
        if args.cmd == "parse":
            print(json.dumps(parse_fares(_read_text(args.file)), indent=2, ensure_ascii=False))
            return 0
        session = browseract.Session(args.session, args.browser)
        run_dir = run_log.resolve_run_dir(args.run)
        state = browseract.status()
        if not args.browser:
            session.browser = browseract.default_browser(state["engine"])

        def on_challenge(current):
            return browseract.handle_challenge(current, logged_in=state["logged_in"], user_reachable=args.attended,
                                               engine=state["engine"])

        result = fare(run_dir, session, args.supersedes, args.url, engine=state["engine"], on_challenge=on_challenge)
        if result is None:
            print("challenge on the fare page; recorded as blocked", file=sys.stderr)
            return 3
        row_id, status, reasons = result
        print(f"{row_id} {status}" + (": " + "; ".join(reasons) if reasons else ""))
    except (ValueError, OSError, UsageError, subprocess.SubprocessError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
