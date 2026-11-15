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

    ok = [r for r in recent if r.get("conclusion") == "success"]
    bad = [r for r in recent if r.get("conclusion") not in (None, "success")]
    latest = recent[-1] if recent else None

    if not recent:
        headline = "**No runs in 24 hours.** The schedule may be disabled."
    elif bad:
        headline = f"**{len(bad)} of {len(recent)} runs failed.**"
    else:
        headline = f"Running normally — {len(recent)} attempts in 24 hours, no capacity yet."

    print(headline)
    print()
    print("| | |")
    print("|---|---|")
    print(f"| Attempts, last 24 h | {len(recent)} |")
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
