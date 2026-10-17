"""A stand-in for the browser-act CLI, installed on PATH by tests (never the real thing).

Behaviour is chosen by environment variables:
  FAKE_BA_SCENARIO  nokey | key | challenge | solved
  FAKE_BA_PAGES     comma-separated files returned by `get markdown`, one per call (last repeats)
  FAKE_BA_LOG       file that receives one line per invocation (the argv)
  FAKE_BA_COUNTER   file holding the number of `get markdown` calls so far
"""
import json
import os
import sys


def main(argv):
    scenario = os.environ.get("FAKE_BA_SCENARIO", "nokey")
    log = os.environ.get("FAKE_BA_LOG")
    if log:
        with open(log, "a", encoding="utf-8") as handle:
            handle.write(" ".join(argv) + "\n")
    args = list(argv)
    session = None
    if args[:1] == ["--session"]:
        session, args = args[1], args[2:]
    cmd = " ".join(args[:2])
    if args[:1] == ["--version"]:
        print("browser-act 1.4.3")
        return 0
    if cmd == "auth poll":
        if scenario in ("key", "challenge", "solved"):
            print("registered")
            return 0
        print("not registered: open the login URL first")
        return 1
    if cmd == "browser list":
        if "--type" in args and args[args.index("--type") + 1] == "stealth" and scenario == "nokey":
            print("API key required for stealth browsers. Sign up: https://browseract.example/signup", file=sys.stderr)
            return 2
        browsers = [{"id": "b-chrome", "type": "chrome", "name": "ffr", "desc": "flight research"}]
        if os.environ.get("FAKE_BA_CHROME_RUNNING"):
            browsers.append({"id": "b-direct", "type": "chrome-direct", "name": "my-chrome", "desc": "user's Chrome"})
        print(json.dumps(browsers))
        return 0
    if cmd == "browser create":
        print(json.dumps({"id": "b-new", "name": args[args.index("--name") + 1] if "--name" in args else "new"}))
        return 0
    if cmd == "session list":
        print(json.dumps([{"name": "ffr-google-1", "browser": "b-chrome"}, {"name": "ffr-kiwi-1", "browser": "b-chrome"},
                          {"name": "other-agent", "browser": "b-chrome"}]))
        return 0
    if cmd == "session close":
        print(f"closed {args[2]}")
        return 0
    if session is None:
        print(f"unknown command: {' '.join(argv)}", file=sys.stderr)
        return 2
    single = args[0] if args else ""
    if cmd in ("browser open", "wait stable") or single in ("navigate", "eval", "input", "click", "keys", "scroll"):
        print("ok")
        return 0
    if cmd == "get markdown":
        pages = [p for p in os.environ.get("FAKE_BA_PAGES", "").split(",") if p]
        counter = os.environ.get("FAKE_BA_COUNTER")
        n = 0
        if counter and os.path.exists(counter):
            n = int(open(counter).read() or 0)
        if counter:
            open(counter, "w").write(str(n + 1))
        if not pages:
            print("# empty")
            return 0
        with open(pages[min(n, len(pages) - 1)], encoding="utf-8") as handle:
            sys.stdout.write(handle.read())
        return 0
    if cmd == "network requests":
        print("[]")
        return 0
    if single == "solve-captcha":
        if scenario == "nokey":
            print("API key required. Sign up: https://browseract.example/signup", file=sys.stderr)
            return 2
        print("solved=True" if scenario == "solved" else "solved=False")
        return 0
    if single == "remote-assist":
        if scenario == "nokey":
            print("API key required", file=sys.stderr)
            return 2
        print("Remote assist ready: https://assist.example/abc")
        return 0
    print(f"unknown command: {' '.join(argv)}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
