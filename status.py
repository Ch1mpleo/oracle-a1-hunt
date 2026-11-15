#!/usr/bin/env python3
"""Turn `gh run list --json` output into a short status report."""

import json
import sys
from datetime import datetime, timedelta, timezone

WINDOW = timedelta(hours=24)


def when(run):
    return datetime.fromisoformat(run["createdAt"].replace("Z", "+00:00"))


def main():
    runs = json.load(open(sys.argv[1], encoding="utf-8"))
    cutoff = datetime.now(timezone.utc) - WINDOW
    recent = sorted((r for r in runs if when(r) >= cutoff), key=when)
    done = [r for r in recent if r.get("conclusion")]

    ok = [r for r in done if r.get("conclusion") == "success"]
    bad = [r for r in done if r.get("conclusion") != "success"]
    latest = done[-1] if done else None

    if not done:
        headline = "**No completed runs in 24 hours.** The schedule may be disabled."
    elif bad:
        headline = f"**{len(bad)} of {len(done)} runs failed.**"
    else:
        headline = f"Running normally — {len(done)} attempts in 24 hours, no capacity yet."

    print(headline)
    print()
    print("| | |")
    print("|---|---|")
    print(f"| Attempts, last 24 h | {len(done)} |")
    print(f"| Failed runs | {len(bad)} |")
    if latest is not None:
        print(f"| Last run | {when(latest).strftime('%H:%M UTC')} — {latest.get('conclusion')} |")
        print(f"| Last run log | {latest.get('url')} |")
    if bad:
        print(f"| Most recent failure | {when(bad[-1]).strftime('%Y-%m-%d %H:%M UTC')} — {bad[-1].get('url')} |")
    print()
    print("A green run means the attempt reached Oracle; `no capacity` is the normal answer in ap-singapore-1.")


if __name__ == "__main__":
    main()
