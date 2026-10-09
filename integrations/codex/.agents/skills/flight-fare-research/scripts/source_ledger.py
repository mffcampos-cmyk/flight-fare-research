#!/usr/bin/env python3
"""Fare-source health ledger for the flight-fare-research skill (stdlib only).

The agent runs the probes with its browser tool; this script only keeps the
books: the canary contract, per-source state, staleness and ladder order.

  source_ledger.py canary [--today YYYY-MM-DD]
  source_ledger.py status [--max-age-days 7] [--json]   exit 0 fresh, 3 probe needed
  source_ledger.py record <id> <state> --evidence TEXT [--url U] [--results N] [--engine NAME]
  source_ledger.py record <new-id> <state> --evidence TEXT --add --name N --role R --family F [--url U]
  source_ledger.py order [--json] [--engine NAME]

--engine names the browser that produced the state (for example
claude-in-chrome, browser-act, headless-playwright): a block on one engine is
not proof of a block on another.

Default ledger (runtime state, kept outside the skill tree so installed or
read-only skill copies never change and raw probe evidence stays local):
  $FFR_LEDGER, else $XDG_STATE_HOME/flight-fare-research/source-status.json,
  else ~/.local/state/flight-fare-research/source-status.json.
The built-in registry seeds a missing or unreadable ledger.
"""
import argparse
import json
import os
import sys
import tempfile
from datetime import date, datetime, timedelta, timezone


def default_ledger():
    if os.environ.get("FFR_LEDGER"):
        return os.environ["FFR_LEDGER"]
    state = os.environ.get("XDG_STATE_HOME") or os.path.join(os.path.expanduser("~"), ".local", "state")
    return os.path.join(state, "flight-fare-research", "source-status.json")


STATES = ("ok", "partial", "blocked", "empty", "error")
AVOID = ("blocked", "empty", "error")
ROLE_RANK = {"discovery": 1, "exact": 2, "ota": 3, "airline": 4, "crosscheck": 5, "opportunistic": 6,
             "positioning": 7, "routes": 8}
HISTORY_MAX = 5
# Browser ladder rungs (references/browser-engines.md): lower is closer to the user's own browser.
ENGINE_RUNG = {"claude-in-chrome": 1, "builtin-browser": 1, "cowork": 1, "browser-act-chrome": 1,
               "browser-act": 2}


def engine_rung(engine):
    if not engine:
        return None
    return ENGINE_RUNG.get(engine, 3 if engine.startswith("headless") else None)

CANARY = {"origin": "ZRH", "destination": "LIS", "lead_days": 30, "trip_days": 7,
          "adults": 1, "cabin": "economy", "currency": "CHF", "trip_type": "round-trip"}

# (id, name, role, family, core, url, seed_state, seed_date, seed_evidence)
REGISTRY = [
    ("flightlist", "FlightList", "discovery", "kiwi", True, "https://www.flightlist.io/",
     "ok", "2026-09-20", "seed: populated discovery cards (historical-observations.md)"),
    ("google-flights", "Google Flights", "exact", "google", True, "https://www.google.com/travel/flights",
     "ok", "2026-09-23", "seed: populated exact-date results, user-observed"),
    ("edreams", "eDreams", "ota", "edreams", True, "https://www.edreams.com/",
     "ok", "2026-09-23", "seed: populated exact-date results, repo test"),
    ("tap-direct", "TAP booking engine", "airline", "tap", True, "https://www.flytap.com/",
     "ok", "2026-09-23", "seed: exact-date fare families with bag, user-observed"),
    ("ita-matrix", "ITA Matrix", "crosscheck", "ita", True, "https://matrix.itasoftware.com/search",
     None, None, None),
    ("azair", "AZair (LCC only)", "opportunistic", "azair", False, "https://www.azair.eu/",
     "partial", "2026-09-20", "seed: loads without bot wall; LCC scope only"),
    ("booking-flights", "Booking.com Flights", "opportunistic", "booking", False,
     "https://flights.booking.com/", None, None, None),
    ("alternative-airlines", "Alternative Airlines", "opportunistic", "altair", False,
     "https://www.alternativeairlines.com/", None, None, None),
    ("kayak", "KAYAK", "opportunistic", "kayak", False, "https://www.kayak.com/",
     "blocked", "2026-09-20", "seed: explicit bot page (kayak.com/help/bots.html)"),
    ("kiwi", "Kiwi.com direct", "opportunistic", "kiwi", False, "https://www.kiwi.com/",
     "blocked", "2026-09-20", "seed: explicit bot/human-check block"),
    ("skyscanner", "Skyscanner", "opportunistic", "skyscanner", False, "https://www.skyscanner.net/",
     "blocked", "2026-09-20", "seed: blocked or empty render"),
    # Expansion candidates: untested until probed (see source-health.md).
    ("lastminute", "lastminute.com", "ota", "lastminute", False, "https://www.lastminute.com/flights",
     None, None, None),
    ("gotogate", "Gotogate/Mytrip", "ota", "etraveli", False, "https://www.gotogate.com/", None, None, None),
    ("aviasales", "Aviasales", "opportunistic", "aviasales", False, "https://www.aviasales.com/",
     None, None, None),
    ("opodo", "Opodo (eDreams group)", "ota", "edreams", False, "https://www.opodo.com/", None, None, None),
    ("momondo", "Momondo (KAYAK group)", "opportunistic", "kayak", False, "https://www.momondo.com/",
     None, None, None),
    ("trip-com", "Trip.com", "opportunistic", "tripcom", False, "https://www.trip.com/flights/", None, None, None),
    ("expedia", "Expedia", "opportunistic", "expedia", False, "https://www.expedia.com/Flights", None, None, None),
    ("swiss-direct", "SWISS", "airline", "swiss", False, "https://www.swiss.com/", None, None, None),
    ("lufthansa-direct", "Lufthansa", "airline", "lufthansa", False, "https://www.lufthansa.com/",
     None, None, None),
    ("easyjet-direct", "easyJet", "airline", "easyjet", False, "https://www.easyjet.com/", None, None, None),
    ("ryanair-direct", "Ryanair", "airline", "ryanair", False, "https://www.ryanair.com/", None, None, None),
    ("vueling-direct", "Vueling", "airline", "vueling", False, "https://www.vueling.com/", None, None, None),
    ("iberia-direct", "Iberia", "airline", "iberia", False, "https://www.iberia.com/", None, None, None),
    ("klm-direct", "KLM", "airline", "klm", False, "https://www.klm.com/", None, None, None),
    ("airfrance-direct", "Air France", "airline", "airfrance", False, "https://wwws.airfrance.fr/",
     None, None, None),
    ("british-airways-direct", "British Airways", "airline", "ba", False, "https://www.britishairways.com/",
     None, None, None),
    ("turkish-direct", "Turkish Airlines (incl. stopover)", "airline", "turkish", False,
     "https://www.turkishairlines.com/", None, None, None),
    ("icelandair-direct", "Icelandair (incl. stopover)", "airline", "icelandair", False,
     "https://www.icelandair.com/", None, None, None),
    ("qatar-direct", "Qatar Airways (incl. stopover)", "airline", "qatar", False,
     "https://www.qatarairways.com/", None, None, None),
    ("sbb", "SBB rail", "positioning", "sbb", False, "https://www.sbb.ch/en", None, None, None),
    ("trainline", "Trainline", "positioning", "trainline", False, "https://www.thetrainline.com/",
     None, None, None),
    ("omio", "Omio", "positioning", "omio", False, "https://www.omio.com/", None, None, None),
    ("flightconnections", "FlightConnections", "routes", "flightconnections", False,
     "https://www.flightconnections.com/", None, None, None),
]


# Expansion probe, 2026-10-08: one paced attempt per source on the canary
# (ZRH-LIS 2026-11-07/14) with headless Playwright Chromium behind a datacenter
# egress proxy (browser ladder rung 3). Blocks here say nothing about the
# user's own browser; see references/source-health.md.
PROBE_ENGINE, PROBE_DATE = "headless-playwright", "2026-10-08"
PROBE = {
    "google-flights": ("ok", "seed: headless probe, ?q= link repeated the search; 10 round-trip cards in CHF"),
    "tap-direct": ("ok", "seed: headless probe, deep link repeated the search; 5 direct flights, CHF per direction"),
    "flightconnections": ("ok", "seed: headless probe, flights-from-zurich-zrh: 218 destinations, 61 airlines"),
    "booking-flights": ("empty", "seed: headless probe, form repeated the search; 'no flights matching' after 45 s"),
    "kiwi": ("empty", "seed: headless probe, deep link loaded (no 403); no results after 45 s"),
    "aviasales": ("empty", "seed: headless probe, deep link repeated route/dates; results never rendered"),
    "kayak": ("blocked", "seed: headless probe, 'Was ist ein Bot?' bot page"),
    "momondo": ("blocked", "seed: headless probe, 'Was ist ein Bot?' bot page"),
    "skyscanner": ("blocked", "seed: headless probe, 'Are you a person or a robot?' press-and-hold"),
    "expedia": ("blocked", "seed: headless probe, HTTP 429 'Bot oder Mensch?'"),
    "trip-com": ("blocked", "seed: headless probe, HTTP 432 'whaleguard block'"),
    "easyjet-direct": ("blocked", "seed: headless probe, HTTP 403 Access Denied on deep link"),
    "lastminute": ("blocked", "seed: headless probe, HTTP 403 Cloudflare challenge"),
    "swiss-direct": ("blocked", "seed: headless probe, HTTP 403 'Security check'"),
    "lufthansa-direct": ("blocked", "seed: headless probe, HTTP 403 'Security check'"),
    "iberia-direct": ("blocked", "seed: headless probe, HTTP 403 'connection was interrupted'"),
    "icelandair-direct": ("blocked", "seed: headless probe, HTTP 403 Cloudflare challenge"),
    "qatar-direct": ("blocked", "seed: headless probe, HTTP 403 Access Denied"),
    "sbb": ("blocked", "seed: headless probe, HTTP 403 with empty body"),
    "omio": ("blocked", "seed: headless probe, HTTP 403 Cloudflare challenge"),
}


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def seed():
    sources = {}
    for sid, name, role, fam, core, url, st, d, ev in REGISTRY:
        engine = None
        if sid in PROBE:
            (st, ev), d, engine = PROBE[sid], PROBE_DATE, PROBE_ENGINE
        checked = f"{d}T12:00:00+00:00" if d else None
        entry = {"name": name, "role": role, "family": fam, "core": core, "url": url,
                 "state": st, "checked_at": checked, "evidence": ev, "results": None,
                 "engine": engine, "history": []}
        if st:
            entry["history"].append({"state": st, "checked_at": checked, "evidence": ev, "engine": engine})
        sources[sid] = entry
    return {"version": 1, "canary": CANARY, "sources": sources}


def load(path):
    if not os.path.exists(path):
        data = seed()
        save(path, data)
        print(f"note: ledger missing, seeded {path}", file=sys.stderr)
        return data
    try:
        with open(path) as f:
            data = json.load(f)
        if not isinstance(data.get("sources"), dict):
            raise ValueError("no sources")
        # add registry sources introduced after the ledger was created
        fresh = seed()["sources"]
        for sid, entry in fresh.items():
            data["sources"].setdefault(sid, entry)
        return data
    except (ValueError, json.JSONDecodeError) as e:
        print(f"warning: ledger unreadable ({e}); reseeding {path}", file=sys.stderr)
        data = seed()
        save(path, data)
        return data


def save(path, data):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(os.path.abspath(path)), suffix=".tmp")
    with os.fdopen(fd, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, path)


def age_days(checked_at):
    if not checked_at:
        return None
    t = datetime.fromisoformat(checked_at)
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - t).total_seconds() / 86400


def cmd_canary(args, _data):
    today = date.fromisoformat(args.today) if args.today else date.today()
    dep = today + timedelta(days=CANARY["lead_days"])
    ret = dep + timedelta(days=CANARY["trip_days"])
    out = {k: v for k, v in CANARY.items() if k not in ("lead_days", "trip_days")}
    out.update({"depart": dep.isoformat(), "return": ret.isoformat(),
                "pass_rule": "ok only if the page repeats route/dates/1 adult/economy/CHF "
                             "and shows >=1 priced itinerary for these exact dates"})
    print(json.dumps(out, indent=2))
    return 0


def stale_core(data, max_age):
    bad = []
    for sid, s in data["sources"].items():
        if not s.get("core"):
            continue
        a = age_days(s.get("checked_at"))
        if a is None:
            bad.append((sid, "untested"))
        elif a > max_age:
            bad.append((sid, f"{a:.1f} days old"))
    return bad


def cmd_status(args, data):
    bad = stale_core(data, args.max_age_days)
    if args.json:
        print(json.dumps({"stale": [{"id": i, "why": w} for i, w in bad],
                          "sources": data["sources"]}, indent=2))
    else:
        print(f"{'source':<24}{'core':<6}{'state':<10}{'age(d)':<8}{'engine':<22}evidence")
        for sid, s in sorted(data["sources"].items(), key=lambda kv: (not kv[1]["core"], kv[0])):
            a = age_days(s.get("checked_at"))
            print(f"{sid:<24}{'yes' if s['core'] else '':<6}{s.get('state') or 'untested':<10}"
                  f"{'-' if a is None else f'{a:.1f}':<8}{(s.get('engine') or '-'):<22}"
                  f"{(s.get('evidence') or '')[:60]}")
        if bad:
            print("\nPROBE NEEDED (core sources): " + ", ".join(f"{i} ({w})" for i, w in bad))
        else:
            print(f"\nLedger fresh (all core sources checked within {args.max_age_days} days).")
    return 3 if bad else 0


def cmd_record(args, data):
    if args.add:
        missing = [f"--{k}" for k in ("name", "role", "family") if not getattr(args, k)]
        if missing:
            print(f"error: --add requires {', '.join(missing)}", file=sys.stderr)
            return 2
        if args.source in data["sources"]:
            print(f"error: source '{args.source}' already exists; record it without --add", file=sys.stderr)
            return 2
        data["sources"][args.source] = {"name": args.name, "role": args.role, "family": args.family,
                                        "core": False, "url": args.url, "state": None, "checked_at": None,
                                        "evidence": None, "results": None, "engine": None, "history": []}
    if args.source not in data["sources"]:
        print(f"error: unknown source '{args.source}'. Known: {', '.join(sorted(data['sources']))}",
              file=sys.stderr)
        return 2
    if args.state == "ok" and (args.results is None or args.results < 1):
        print("error: state 'ok' requires --results N (N >= 1 priced itineraries seen)", file=sys.stderr)
        return 2
    s = data["sources"][args.source]
    ts = now_iso()
    s.update({"state": args.state, "checked_at": ts, "evidence": args.evidence,
              "results": args.results, "engine": args.engine})
    if args.url:
        s["probe_url"] = args.url
    s["history"] = ([{"state": args.state, "checked_at": ts, "evidence": args.evidence,
                      "results": args.results, "engine": args.engine}] + s.get("history", []))[:HISTORY_MAX]
    save(args.ledger, data)
    print(f"recorded {args.source}: {args.state} at {ts}" + (f" ({args.engine})" if args.engine else ""))
    return 0


def cmd_order(args, data):
    def key(item):
        sid, s = item
        return (not s["core"], ROLE_RANK.get(s["role"], 9), sid)
    items = sorted(data["sources"].items(), key=key)
    fields = ("name", "role", "family", "state", "checked_at")
    use = [dict(id=i, engine=s.get("engine"), **{k: s[k] for k in fields})
           for i, s in items if s.get("state") == "ok"]
    use += [dict(id=i, engine=s.get("engine"), **{k: s[k] for k in fields})
            for i, s in items if s.get("state") == "partial"]
    untested = [dict(id=i, name=s["name"], role=s["role"]) for i, s in items if not s.get("state")]
    mine = engine_rung(args.engine)
    avoid, reprobe = [], []
    for i, s in items:
        if s.get("state") not in AVOID:
            continue
        entry = dict(id=i, name=s["name"], state=s["state"], checked_at=s["checked_at"],
                     engine=s.get("engine"), evidence=s.get("evidence"))
        theirs = engine_rung(s.get("engine"))
        (reprobe if mine and theirs and mine < theirs else avoid).append(entry)
    if args.json:
        print(json.dumps({"use": use, "untested": untested, "reprobe": reprobe, "avoid": avoid}, indent=2))
        return 0
    print("USE (in order):")
    for n, s in enumerate(use, 1):
        print(f"  {n}. {s['id']:<22} {s['role']:<13} family={s['family']:<12} {s['state']:<8}"
              f" engine={s.get('engine') or '-'}")
    print("UNTESTED (one probe allowed if needed): " + (", ".join(u["id"] for u in untested) or "-"))
    if reprobe:
        print(f"RE-PROBE ALLOWED on {args.engine} (failed only on a lower rung): "
              + ", ".join(s["id"] for s in reprobe))
    print("AVOID this run unless re-probed:")
    for s in avoid:
        hint = ("  [lower-rung result: one probe allowed in the user's own browser]"
                if (engine_rung(s.get("engine")) or 0) > 1 and not mine else "")
        print(f"  - {s['id']:<22} {s['state']:<8} {(s['checked_at'] or '')[:10]}  "
              f"engine={s.get('engine') or '-'}  {s['evidence']}{hint}")
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--ledger", default=None, help="ledger path (default: see module docstring)")
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("canary"); c.add_argument("--today")
    s = sub.add_parser("status"); s.add_argument("--max-age-days", type=float, default=7)
    s.add_argument("--json", action="store_true")
    r = sub.add_parser("record"); r.add_argument("source"); r.add_argument("state", choices=STATES)
    r.add_argument("--evidence", required=True); r.add_argument("--url"); r.add_argument("--results", type=int)
    r.add_argument("--engine", help="browser engine that produced this state")
    r.add_argument("--add", action="store_true", help="register a source missing from the registry")
    r.add_argument("--name"); r.add_argument("--role", choices=sorted(ROLE_RANK)); r.add_argument("--family")
    o = sub.add_parser("order"); o.add_argument("--json", action="store_true")
    o.add_argument("--engine", help="your engine: failures recorded only on a lower rung become re-probes")
    args = p.parse_args(argv)
    args.ledger = args.ledger or default_ledger()
    data = load(args.ledger) if args.cmd != "canary" else None
    return {"canary": cmd_canary, "status": cmd_status, "record": cmd_record, "order": cmd_order}[args.cmd](args, data)


if __name__ == "__main__":
    sys.exit(main())
