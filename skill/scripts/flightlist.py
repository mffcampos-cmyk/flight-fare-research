#!/usr/bin/env python3
"""FlightList result cards to run_log.py rows (stdlib only).

One FlightList search with a departure range and a return range lists the
cheapest itineraries across every date pair in it, with both directions. This
script turns those cards into rows so a whole flexible window is recorded from
one search instead of one search per pair.

  flightlist.py rows --run DIR [--top N] [--cabin C] [--hack H] [--engine E] FILE|-
      FILE is the JSON the extraction snippet in references/flightlist-browser.md
      returns (one object per li.flight: price, text, book). Prints a JSON array of
      rows for `run_log.py add --row -`: per date pair of the run, the N cheapest
      cards within the duration cap, plus the cheapest card overall when it breaks
      the cap and is cheaper (kept so the rejection is on record). Pairs with no
      card are listed on stderr: search them separately.
  flightlist.py parse FILE|-
      The cards as JSON (both directions, segment flight numbers).

Every row is a list fare with baggage unverified, whatever the bag filter said:
qualify it on the Kiwi fare page or the airline. Exit 0 ok, 2 usage error.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import date, datetime, timedelta, timezone

sys.dont_write_bytecode = True  # never leave __pycache__ inside the skill folder
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_log  # noqa: E402

MONTHS = {m: n for n, m in enumerate("Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split(), 1)}
PRICE = re.compile(r"^([A-Z]{3})\s?([\d,.]+)")
SUMMARY = re.compile(r"(\d{1,2}:\d{2}[ap]m) - (\d{1,2}:\d{2}[ap]m) \w{3} (\w{3}) (\d{1,2})(?:st|nd|rd|th) (\d{4}) "
                     r"(\d+)h (\d+)m [^(]+\(([A-Z]{3})\) → [^(]+\(([A-Z]{3})\) (Direct|(\d+) Stops?)")
SEGMENT = re.compile(r"\w{3} (\w{3}) (\d{1,2})(?:st|nd|rd|th) (\d{4}) ([^·()]+?) · ([A-Z0-9]{2} ?\d+) "
                     r"Depart at (\d{1,2}:\d{2}[ap]m) from [^(]+\(([A-Z]{3})\) Fly for (\d+)h (\d+)m "
                     r"Arrive at (\d{1,2}:\d{2}[ap]m) in [^(]+\(([A-Z]{3})\)")


def _clock(text: str) -> tuple[int, int]:
    hours, minutes = text[:-2].split(":")
    return int(hours) % 12 + (12 if text.endswith("pm") else 0), int(minutes)


def _stamp(day: date, clock: tuple[int, int]) -> str:
    return f"{day.isoformat()}T{clock[0]:02d}:{clock[1]:02d}:00"


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
    if len(summaries) < 2 or stay < 0 or not segments:
        raise ValueError(f"card without both directions: {text[:80]!r}")
    directions = []
    for name, summary, part in (("out", summaries[0], [g for at, g in segments if at < stay]),
                                ("ret", summaries[1], [g for at, g in segments if at > stay])):
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
            "stops": 0 if summary[9] == "Direct" else int(summary[10]),
            "airlines": airlines, "flights": [seg[4] for seg in part],
            "airport_change": any(a[10] != b[6] for a, b in zip(part, part[1:])),
            "mixed_carriers": len(airlines) > 1})
    return {"price": float(price.group(2).replace(",", "")), "currency": price.group(1),
            "book": card.get("book") if isinstance(card, dict) else None, "directions": directions}


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
    out, ret = card["directions"]
    notes = [f"FlightList card; flights {' '.join(out['flights'])} / {' '.join(ret['flights'])}",
             "bag filter does not prove the bag is in the price"]
    for d in card["directions"]:
        if d["mixed_carriers"]:
            notes.append(f"{d['dir']}: {', '.join(d['airlines'])} (Kiwi combination: possible self-transfer, "
                         "confirm on the Kiwi page)")
    directions = [{k: d[k] for k in ("dir", "from", "to", "dep", "arr", "duration", "stops", "airlines",
                                     "airport_change")} | {"self_transfer": False} for d in card["directions"]]
    return dict(base, outcome="populated", origin=out["from"], destination=out["to"],
                outbound_date=out["dep"][:10], return_date=ret["dep"][:10], currency=card["currency"], fx=None,
                price_basis="total",
                tickets=[{"price": card["price"], "quote_state": "list", "provider": "Kiwi.com (via FlightList)",
                          "baggage": "unverified", "bag_fee": None, "booking_url": card["book"] or base["url"]}],
                directions=directions, components={}, notes="; ".join(notes))


def rows_for(contract: dict, raw_cards: list, *, top: int = 1, cabin: str | None = None, hack: str | None = None,
             engine: str = "browser", retrieved_at: str | None = None) -> tuple[list[dict], list[str]]:
    """Rows per date pair of the contract, and the pairs no card covered."""
    contract = run_log.normalize_contract(contract)
    cap = contract.get("max_duration")
    base = {"source": "flightlist", "family": "kiwi", "engine": engine, "url": "https://www.flightlist.io/",
            "retrieved_at": retrieved_at or datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "cabin": cabin or contract["cabins"][0], "cabin_label": (cabin or contract["cabins"][0]).capitalize(),
            "hack": hack}
    parsed = sorted((parse_card(c) for c in raw_cards), key=lambda c: c["price"])
    by_pair: dict[tuple, list] = {}
    for card in parsed:
        key = (card["directions"][0]["dep"][:10], card["directions"][1]["dep"][:10])
        by_pair.setdefault(key, []).append(card)
    rows, missing = [], []
    for out_date, ret_date in run_log.expand_dates(contract["dates"], contract["trip_type"]):
        found = by_pair.get((out_date, ret_date), [])
        if not found:
            missing.append(f"{out_date}_{ret_date}")
            continue
        within = [c for c in found if _within(c, cap)]
        chosen = within[:top]
        if not within or found[0]["price"] < within[0]["price"]:
            chosen = [found[0]] + chosen
        rows.extend(_row(c, base) for c in chosen)
    return rows, missing


def _load(path: str):
    try:
        text = sys.stdin.read() if path == "-" else open(path, encoding="utf-8").read()
        data = json.loads(text)
    except (OSError, ValueError) as exc:
        raise run_log.UsageError(f"cannot read cards from {path}: {exc}")
    if not isinstance(data, list):
        raise run_log.UsageError("cards must be a JSON array")
    return data


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("rows", help="cards to run_log rows (JSON array on stdout)")
    p.add_argument("--run", help="run directory (default: most recent run)")
    p.add_argument("--top", type=int, default=1, help="cards within the cap kept per date pair (default 1)")
    p.add_argument("--cabin", help="cabin searched (default: the contract's first cabin)")
    p.add_argument("--hack", help="hack these rows belong to, e.g. nearby_origin")
    p.add_argument("--engine", default="browser", help="browser engine used, as in source_ledger.py")
    p.add_argument("file")
    p = sub.add_parser("parse", help="cards to JSON")
    p.add_argument("file")
    args = parser.parse_args(argv)
    try:
        cards = _load(args.file)
        if args.cmd == "parse":
            print(json.dumps([parse_card(c) for c in cards], indent=2, ensure_ascii=False))
            return 0
        contract = run_log.load_run(run_log.resolve_run_dir(args.run))[0]
        rows, missing = rows_for(contract, cards, top=args.top, cabin=args.cabin, hack=args.hack, engine=args.engine)
        print(json.dumps(rows, ensure_ascii=False))
        print(f"{len(rows)} rows for {len(run_log.expand_dates(contract['dates'], contract['trip_type'])) - len(missing)}"
              " date pair(s)", file=sys.stderr)
        for pair in missing:
            print(f"no card for {pair}: search it separately", file=sys.stderr)
    except (ValueError, run_log.UsageError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
