#!/usr/bin/env python3
"""Run evidence log for the flight-fare-research skill (stdlib only, no network).

The agent performs every search; this script only keeps one run's books: the
search contract (legs, airport groups, dates), the expected comparisons, every
observation row, the computed lead/qualified status of each row, and whether
the run is complete. The rules live in ffr_contract.py and ffr_rows.py.

  run_log.py init --contract FILE [--runs-root DIR]
  run_log.py shortlist --run DIR CODE[,CODE...]      gateways for a region group
  run_log.py confirm --run DIR [--top N]             tuples to confirm, from discovery rows
  run_log.py add --row FILE|- [--run DIR]            fare rows, ground rows and attempts
  run_log.py resolve CELL --as na|no_fare|none_qualify --reason TEXT [--run DIR]
  run_log.py coverage [--run DIR] [--json]
  run_log.py rank [--run DIR] [--cabin C] [--top N] [--json]
  run_log.py check [--run DIR] [--json]              exit 0 complete, 4 incomplete
  run_log.py jobs [--run DIR] [--sessions N] [--top N] [--json]   parallel job plan

Exit 2 means a usage or validation error. Runs live in $FFR_RUNS, else
$XDG_STATE_HOME/flight-fare-research/runs, else
~/.local/state/flight-fare-research/runs; --run defaults to the most recently
modified run directory there.
"""
from __future__ import annotations

import argparse
import contextlib
import json
import os
import sys
from datetime import datetime

sys.dont_write_bytecode = True  # never leave __pycache__ inside the skill folder
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ffr_contract as fc  # noqa: E402
import ffr_rows as fr  # noqa: E402

UsageError = fc.UsageError
EXIT_OK, EXIT_USAGE, EXIT_INCOMPLETE = 0, 2, 4
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
SESSIONS_PER_SITE = {"google-flights": 1}  # the daily allowance: confirmation only, one session
KIWI_FARE_URL = "kiwi.com/"


def runs_root() -> str:
    if os.environ.get("FFR_RUNS"):
        return os.environ["FFR_RUNS"]
    state = os.environ.get("XDG_STATE_HOME") or os.path.join(os.path.expanduser("~"), ".local", "state")
    return os.path.join(state, "flight-fare-research", "runs")


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


def write_contract(run_dir: str, contract: dict) -> None:
    path = os.path.join(run_dir, "contract.json")
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(contract, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    os.replace(tmp, path)


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


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


# --------------------------------------------------------------------------- add

def _read_json(path: str):
    try:
        if path == "-":
            return json.load(sys.stdin)
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError) as exc:
        raise UsageError(f"cannot read JSON from {path}: {exc}")


def _read_rows(path: str) -> list:
    """One row object, a JSON array of rows, or JSON Lines (one row per line)."""
    try:
        text = sys.stdin.read() if path == "-" else open(path, encoding="utf-8").read()
    except OSError as exc:
        raise UsageError(f"cannot read rows from {path}: {exc}")
    try:
        data = json.loads(text)
    except ValueError:
        try:
            data = [json.loads(line) for line in text.splitlines() if line.strip()]
        except ValueError as exc:
            raise UsageError(f"cannot read JSON from {path}: {exc}")
    return data if isinstance(data, list) else [data]


def add_rows(run_dir: str, rows: list) -> list[tuple[str, str, list[str]]]:
    """Validate every row (fare, attempt or ground), then append them all (or nothing).
    Caller holds the run lock. Returns (id, status, reasons) per row, in order."""
    contract, records = load_run(run_dir)
    row_ids = {r["id"] for r in records if r.get("type") == "row"}
    ground_ids = {r["id"] for r in records if r.get("type") == "ground"}
    problems = []
    for n, row in enumerate(rows, 1):
        if isinstance(row, dict) and row.get("kind") == "ground":
            errors = fr.validate_ground(row, contract)
        else:
            errors = fr.validate_row(row, contract)
            if isinstance(row, dict) and row.get("supersedes") and row["supersedes"] not in row_ids:
                errors.append(f"supersedes names {row['supersedes']}, which is not in this run")
        label = f"row {n}: " if len(rows) > 1 else ""
        problems.extend(f"{label}{e}" for e in errors)
    if not rows:
        problems.append("no rows given")
    if problems:
        raise UsageError("invalid row (nothing saved):\n" + "\n".join(f"  - {e}" for e in problems))
    stamp = _now()
    added = []
    for row in rows:
        if row.get("kind") == "ground":
            record = dict(row, type="ground", id=f"g{len(ground_ids) + 1}", added_at=stamp)
            ground_ids.add(record["id"])
        else:
            record = dict(row, type="row", id=f"r{len(row_ids) + 1}", added_at=stamp)
            row_ids.add(record["id"])
        append_record(run_dir, record)
        records.append(record)
        added.append(record)
    superseded, grounds = fr.superseded_ids(records), fr.grounds_of(records)
    out = []
    for r in added:
        if r["type"] == "ground":
            out.append((r["id"], r["quote_state"], [f"{r['from']}-{r['to']} {r['date']} {r['price']:.2f} {r['currency']}"]))
        else:
            out.append((r["id"], *fr.row_status(r, contract, superseded, grounds)))
    return out


def cmd_add(args) -> int:
    run_dir = resolve_run_dir(args.run)
    rows = _read_rows(args.row)
    with locked(run_dir):
        for row_id, status, reasons in add_rows(run_dir, rows):
            sep = " " if row_id.startswith("g") else ": "
            print(f"{row_id} {status}" + (sep + "; ".join(reasons) if reasons else ""))
    return EXIT_OK


# --------------------------------------------------------------------------- init, shortlist, confirm

def cmd_init(args) -> int:
    contract = _read_json(args.contract)
    errors = fc.validate_contract(contract)
    if errors:
        raise UsageError("invalid contract:\n" + "\n".join(f"  - {e}" for e in errors))
    c = fc.normalize_contract(contract)
    c["date_tuples"] = fc.expand_tuples(c)
    c["cells"] = fc.build_cells(c)
    run_dir = os.path.join(args.runs_root or runs_root(), c["run_id"])
    if os.path.exists(run_dir):
        raise UsageError(f"run directory already exists: {run_dir} (choose another run_id)")
    os.makedirs(run_dir)
    write_contract(run_dir, c)
    open(os.path.join(run_dir, "rows.jsonl"), "w", encoding="utf-8").close()
    auto = sum(1 for cell in c["cells"] if cell["auto"])
    print(run_dir)
    print(f"{len(c['date_tuples'])} date tuple(s), {len(c['cells'])} comparison cell(s), {auto} not applicable; "
          f"shape {c['shape']}, speed {c['speed']}")
    regions = fc.region_groups(c)
    if regions:
        print(f"{len(regions)} region group(s) awaiting a shortlist: after discovery run "
              f"run_log.py shortlist --run {run_dir} CODE,CODE,...")
    return EXIT_OK


def cmd_shortlist(args) -> int:
    run_dir = resolve_run_dir(args.run)
    codes = [c.strip() for c in args.codes.split(",") if c.strip()]
    with locked(run_dir):
        contract, _ = load_run(run_dir)
        try:
            c = fc.apply_shortlist(contract, codes)
        except ValueError as exc:
            raise UsageError(f"shortlist refused: {exc}")
        write_contract(run_dir, c)
        append_record(run_dir, {"type": "contract", "at": _now(), "shortlist": codes})
    print(f"shortlist {', '.join(codes)}: {len(c['date_tuples'])} date tuple(s), {len(c['cells'])} comparison cell(s)")
    return EXIT_OK


def cmd_confirm(args) -> int:
    run_dir = resolve_run_dir(args.run)
    with locked(run_dir):
        contract, records = load_run(run_dir)
        picks = fr.pick_confirm_tuples(contract, records, top=args.top)
        if not picks:
            raise UsageError("no discovery rows to pick from yet (rows with \"phase\": \"discover\"); "
                             "run the discover sweeps first")
        try:
            c = fc.fill_confirm_cells(contract, picks)
        except ValueError as exc:
            raise UsageError(f"confirm refused: {exc}")
        write_contract(run_dir, c)
        append_record(run_dir, {"type": "contract", "at": _now(), "confirm": picks})
    for key, tuples in sorted(picks.items()):
        cabin, dest = key.split("/", 1)
        print(f"{cabin}/confirm/{dest}: " + ", ".join(fc.tuple_id(t) for t in tuples))
    return EXIT_OK


# --------------------------------------------------------------------------- rank, resolve, coverage, check

def _trip_text(row: dict) -> str:
    return f"{row.get('origin')}-{row.get('destination')} {'/'.join(row.get('dates') or [])}"


def _leg_lines(row: dict, indent: str) -> list[str]:
    lines = []
    for leg in row.get("legs") or []:
        if not isinstance(leg, dict):
            continue
        dep, arr = str(leg.get("dep") or "?").replace("T", " ")[:16], str(leg.get("arr") or "?").replace("T", " ")[:16]
        stops = leg.get("stops")
        stop_text = f"{stops} stop" + ("" if stops == 1 else "s")
        airlines = leg.get("airlines")
        airlines = ", ".join(airlines) if isinstance(airlines, list) else str(airlines or "")
        part = f" part {leg.get('part')}" if (leg.get("part") or 1) > 1 else ""
        lines.append(f"{indent}leg {leg.get('leg')}{part} {dep} -> {arr}  {str(leg.get('duration'))[:5]}  "
                     f"{stop_text}  {airlines}")
    return lines


def _ground_lines(entry: dict, records: list[dict], indent: str) -> list[str]:
    by_id = {r["id"]: r for r in records if r.get("type") == "ground"}
    lines = []
    for code, chosen in entry.get("ground", {}).items():
        for gid in chosen:
            g = by_id.get(gid)
            lines.append(f"{indent}ground {code}: " + (f"{g['from']}-{g['to']} {g['date']} {g['price']:.2f} {g['currency']} ({gid})"
                                                        if g else "unpriced"))
    return lines


def cmd_rank(args) -> int:
    contract, records = load_run(resolve_run_dir(args.run))
    if args.cabin and args.cabin not in contract["cabins"]:
        raise UsageError(f"cabin {args.cabin} is not in this run's contract")
    if args.top is not None and args.top < 0:
        raise UsageError("--top must be 0 or more")
    ranked = fr.rank(contract, records, args.cabin)
    if args.json:
        print(json.dumps({cab: {"best": v["best"], "qualified": [fr.public_entry(e) for e in v["qualified"]],
                                "leads": [fr.public_entry(e) for e in v["leads"]]} for cab, v in ranked.items()},
                         indent=2, ensure_ascii=False))
        return EXIT_OK
    cur = contract["currency"]
    for cab, v in ranked.items():
        print(f"== {cab}: qualified (all-in {cur})")
        for n, e in enumerate(v["qualified"], 1):
            row = e["row"]
            hack = f" [{row['hack']}]" if row.get("hack") else ""
            print(f"  {n}. {e['id']}{hack} {e['all_in']:.2f} {row.get('source')} {_trip_text(row)}"
                  f"  retrieved {row.get('retrieved_at')}")
            for line in _leg_lines(row, "       ") + _ground_lines(e, records, "       "):
                print(line)
            sellers = ", ".join(t.get("provider") or "?" for t in row.get("tickets") or [])
            links = " ".join(t.get("booking_url") for t in row.get("tickets") or [] if t.get("booking_url"))
            print(f"       seller: {sellers}  book: {links or '-'}")
            if e["flags"]:
                print(f"       flags: {', '.join(e['flags'])}")
        if not v["qualified"]:
            print("  (none)")
        print(f"== {cab}: leads (not verified; lower bound, never a price)")
        shown = v["leads"] if args.top is None else v["leads"][:args.top]
        for e in shown:
            row = e["row"]
            hack = f" [{row['hack']}]" if row.get("hack") else ""
            pruned = f"  pruned: LB {e['lower_bound']:.2f} >= best {v['best']:.2f}" if e["pruned"] else ""
            note = "" if e["comparable"] else "  (no fx: not comparable)"
            print(f"  {e['id']}{hack} LB {e['lower_bound']:.2f} {e['currency']} {_trip_text(row)}: "
                  f"{'; '.join(e['reasons'])}{pruned}{note}")
            for line in _leg_lines(row, "      "):
                print(line)
        if len(shown) < len(v["leads"]):
            print(f"  (+{len(v['leads']) - len(shown)} more leads)")
        if not v["leads"]:
            print("  (none)")
    return EXIT_OK


def cmd_resolve(args) -> int:
    run_dir = resolve_run_dir(args.run)
    with locked(run_dir):
        contract, records = load_run(run_dir)
        cells = {c["id"]: c for c in contract.get("cells") or fc.build_cells(contract)}
        if args.cell not in cells:
            raise UsageError(f"unknown cell {args.cell}; see run_log.py coverage")
        refusal = fr.resolve_guard(cells[args.cell], getattr(args, "as"), contract, records)
        if refusal:
            raise UsageError(refusal)
        append_record(run_dir, {"type": "resolve", "cell": args.cell, "as": getattr(args, "as"),
                                "reason": args.reason, "at": _now()})
    print(f"resolved {args.cell} as {getattr(args, 'as')}: {args.reason}")
    return EXIT_OK


def cmd_coverage(args) -> int:
    contract, records = load_run(resolve_run_dir(args.run))
    states = fr.cell_states(contract, records)
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
    result = fr.check(contract, records)
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


# --------------------------------------------------------------------------- jobs

def _script(name: str) -> str:
    return f"python3 {os.path.join(SCRIPTS_DIR, name)}"


def plan_jobs(contract: dict, records: list[dict], run_dir: str, sessions_per_site: int = 2,
              top: int = 3) -> list[dict]:
    """One job per parallel session: its source family and the commands that close its cells."""
    states = {s["id"]: s for s in fr.cell_states(contract, records)}
    cells = {c["id"]: c for c in contract.get("cells") or fc.build_cells(contract)}
    open_ids = [cid for cid, s in states.items() if s["state"] == "open"]
    jobs: list[dict] = []

    def job(source: str, family: str, session: str, hint: str = "") -> dict:
        for j in jobs:
            if j["session"] == session:
                return j
        j = {"session": session, "source": source, "family": family, "commands": [], "cells": [], "note": hint}
        jobs.append(j)
        return j

    def spread(source: str, family: str, items: list[tuple[str, str]]) -> None:
        """Round-robin (command, cell) pairs over this site's sessions."""
        n = SESSIONS_PER_SITE.get(source, sessions_per_site)
        for i, (command, cell) in enumerate(items):
            j = job(source, family, f"ffr-{source.split('-')[0]}-{i % n + 1}")
            j["commands"].append(command)
            j["cells"].append(cell)

    origins = "+".join(fc.airports(contract["legs"][0]["from"]))
    discover = [(f"{_script('flightlist.py')} sweep --session ffr-flightlist-{{n}} --run {run_dir} "
                 f"--cabin {cells[cid]['cabin']} --from {origins} --to {cells[cid]['destination']}", cid)
                for cid in open_ids if cells.get(cid, {}).get("kind") == "discover"]
    n_fl = SESSIONS_PER_SITE.get("flightlist", sessions_per_site)
    spread("flightlist", "kiwi", [(cmd.replace("{n}", str(i % n_fl + 1)), cid) for i, (cmd, cid) in enumerate(discover)])

    confirm_waiting = [cid for cid in open_ids if cells.get(cid, {}).get("kind") == "confirm" and not cells[cid].get("tuples")]
    if confirm_waiting and not discover:
        j = job("run_log", "-", "ffr-run_log", "after the discover sweeps")
        j["commands"].append(f"{_script('run_log.py')} confirm --run {run_dir} --top {top}")
        j["cells"].extend(confirm_waiting)
    elif confirm_waiting:
        j = job("run_log", "-", "ffr-run_log", "after the discover sweeps")
        j["commands"].append(f"{_script('run_log.py')} confirm --run {run_dir} --top {top}")
        j["cells"].extend(confirm_waiting)

    google: dict[tuple[str, str], list[str]] = {}
    google_cells: dict[tuple[str, str], list[str]] = {}
    for cid in open_ids:
        cell = cells.get(cid)
        if not cell:
            continue
        if cell["kind"] == "confirm" and cell.get("tuples"):
            missing = [t for t in cell["tuples"]
                       if fc.tuple_id(t) in states[cid]["why"]] or cell["tuples"]
            key = (cell["cabin"], cell["destination"])
            google.setdefault(key, []).extend(fc.tuple_id(t) for t in missing)
            google_cells.setdefault(key, []).append(cid)
        elif cell["kind"] == "baseline":
            key = (cell["cabin"], cell["destination"])
            google.setdefault(key, []).append(fc.tuple_id(cell["dates"]))
            google_cells.setdefault(key, []).append(cid)
    for (cabin, dest), tuples in google.items():
        j = job("google-flights", "google", "ffr-google-1", "one session: Google's daily allowance")
        j["commands"].append(f"{_script('gflights.py')} sweep --session ffr-google-1 --run {run_dir} "
                             f"--cabins {cabin} --destination {dest} --tuples {','.join(dict.fromkeys(tuples))}")
        j["cells"].extend(google_cells[(cabin, dest)])

    ranked = fr.rank(contract, records)
    reprice_open = [cid for cid in open_ids if cells.get(cid, {}).get("kind") == "reprice"]
    for cid in reprice_open:
        cabin = cells[cid]["cabin"]
        leads = [e for e in ranked.get(cabin, {}).get("leads", []) if not e["pruned"]]
        kiwi = [(e["id"], t["booking_url"]) for e in leads for t in e["row"].get("tickets") or []
                if KIWI_FARE_URL in str(t.get("booking_url") or "")]
        if kiwi:
            spread("kiwi", "kiwi", [(f"{_script('kiwi.py')} fare --session ffr-kiwi-{{n}} --run {run_dir} "
                                     f"--supersedes {rid} {url}", cid) for rid, url in kiwi[:top]])
            for j in jobs:
                if j["source"] == "kiwi":
                    j["commands"] = [c.replace("{n}", j["session"].rsplit("-", 1)[1]) for c in j["commands"]]
        else:
            j = job("recipe", "-", "ffr-reprice", "reprice the shortlist on the sellers' pages")
            j["commands"].append(f"see references/qualification.md and references/airline-direct.md for cabin {cabin}")
            j["cells"].append(cid)
    for cid in open_ids:
        kind = cells.get(cid, {}).get("kind")
        if kind == "hack":
            j = job("recipe", "-", "ffr-hacks", "route hacks by hand, one Google session")
            j["commands"].append(f"see references/route-hacks.md for {cid}")
            j["cells"].append(cid)
        elif kind == "crosscheck":
            j = job("recipe", "-", "ffr-crosscheck", "a second independent source family")
            j["commands"].append(f"see references/source-ladder.md: second family for {cells[cid]['cabin']}")
            j["cells"].append(cid)
    return jobs


def cmd_jobs(args) -> int:
    run_dir = resolve_run_dir(args.run)
    contract, records = load_run(run_dir)
    if args.sessions < 1 or args.top < 1:
        raise UsageError("--sessions and --top must be 1 or more")
    jobs = plan_jobs(contract, records, run_dir, sessions_per_site=args.sessions, top=args.top)
    if args.json:
        print(json.dumps(jobs, indent=2, ensure_ascii=False))
        return EXIT_OK
    if not jobs:
        print("no open comparisons: run run_log.py check")
    for j in jobs:
        note = f"  ({j['note']})" if j["note"] else ""
        print(f"== session {j['session']}  source {j['source']}  family {j['family']}{note}")
        for command in j["commands"]:
            print(f"   {command}")
        print(f"   cells: {', '.join(j['cells'])}")
    return EXIT_OK


# --------------------------------------------------------------------------- cli

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("init", help="validate a contract and create a run")
    p.add_argument("--contract", required=True, help="contract JSON file, or - for stdin")
    p.add_argument("--runs-root", help="directory holding runs (default: see module docstring)")
    p.set_defaults(func=cmd_init)
    p = sub.add_parser("shortlist", help="add discovered gateway airports to a region group")
    p.add_argument("codes", help="comma-separated IATA codes, e.g. BKK,SIN")
    p.add_argument("--run", help="run directory (default: most recent run)")
    p.set_defaults(func=cmd_shortlist)
    p = sub.add_parser("confirm", help="choose the cheapest discovered tuples to confirm on an exact-date source")
    p.add_argument("--run", help="run directory (default: most recent run)")
    p.add_argument("--top", type=int, default=3, help="tuples per cabin and destination (default 3)")
    p.set_defaults(func=cmd_confirm)
    p = sub.add_parser("add", help="append rows (fare, ground, attempt); saved immediately; all or nothing")
    p.add_argument("--row", required=True,
                   help="row JSON file, or - for stdin: one object, a JSON array, or JSON Lines")
    p.add_argument("--run", help="run directory (default: most recent run)")
    p.set_defaults(func=cmd_add)
    p = sub.add_parser("rank", help="qualified options by all-in total, then leads")
    p.add_argument("--run", help="run directory (default: most recent run)")
    p.add_argument("--cabin", help="only this cabin")
    p.add_argument("--top", type=int, help="list at most N leads per cabin (text output)")
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
    p = sub.add_parser("jobs", help="plan parallel sessions for the open comparisons")
    p.add_argument("--run", help="run directory (default: most recent run)")
    p.add_argument("--sessions", type=int, default=2, help="parallel sessions per site (Google always 1)")
    p.add_argument("--top", type=int, default=3, help="tuples to confirm, leads to reprice (default 3)")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_jobs)
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
