"""Shared builders for run_log tests (synthetic data, no network)."""
import json, os, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skill" / "scripts" / "run_log.py"
sys.dont_write_bytecode = True  # never leave __pycache__ inside skill/
sys.path.insert(0, str(SCRIPT.parent))
import run_log  # noqa: E402

def contract(**over):
    c = {"run_id": "t1", "scope": "quick", "trip_type": "return",
         "travelers": {"adults": 1, "children_ages": [], "infants": 0},
         "currency": "CHF", "origins": ["AAA"], "nearby_origins": [],
         "destinations": ["ZZZ"], "alt_destinations": [],
         "dates": {"pairs": [["2026-11-05", "2026-11-12"]]},
         "cabins": ["economy"], "bags": {"checked_per_person": 1},
         "max_duration": {"value": "20:00:00", "strict": True},
         "positioning": {"allowed": False, "rail_ok": False, "overnight_ok": False},
         "self_transfer_ok": False, "event": None, "assumptions": []}
    c.update(over)
    return c

def direction(dir="out", **over):
    base = {"out": {"from": "AAA", "to": "ZZZ", "dep": "2026-11-05T07:10:00",
                    "arr": "2026-11-05T09:05:00", "duration": "02:55:00"},
            "ret": {"from": "ZZZ", "to": "AAA", "dep": "2026-11-12T18:00:00",
                    "arr": "2026-11-12T22:00:00", "duration": "03:00:00"}}[dir]
    d = dict(base, dir=dir, stops=0, airlines=["XX"], airport_change=False, self_transfer=False)
    d.update(over)
    return d

def ticket(**over):
    t = {"price": 400.0, "quote_state": "completed", "provider": "XX",
         "baggage": "included", "bag_fee": None, "booking_url": "https://example.test/book"}
    t.update(over)
    return t

def row(**over):
    r = {"source": "google-flights", "family": "google", "engine": "test", "outcome": "populated",
         "url": "https://example.test/search", "retrieved_at": "2026-10-08T14:03:00+02:00",
         "cabin": "economy", "cabin_label": "Economy", "hack": None,
         "origin": "AAA", "destination": "ZZZ",
         "outbound_date": "2026-11-05", "return_date": "2026-11-12",
         "currency": "CHF", "fx": None, "price_basis": "total",
         "tickets": [ticket()], "directions": [direction("out"), direction("ret")],
         "components": {}, "positioning_overnight": False, "supersedes": None, "notes": ""}
    r.update(over)
    return r

def records(*rows):
    return [dict(r, type="row", id=f"r{i}") for i, r in enumerate(rows, 1)]

def write_json(path, obj):
    path = Path(path); path.write_text(json.dumps(obj)); return path

def cli(*args, env=None, input=None):
    e = {k: v for k, v in os.environ.items() if k not in ("FFR_RUNS", "XDG_STATE_HOME")}
    e.update(env or {})
    return subprocess.run([sys.executable, str(SCRIPT), *map(str, args)],
                          capture_output=True, text=True, env=e, input=input)
