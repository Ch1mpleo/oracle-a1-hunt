#!/usr/bin/env python3
"""Turn `gh run list --json` output into a short status report."""

import json
import sys
from datetime import datetime, timedelta, timezone

WINDOW = timedelta(hours=24)
STALE_AFTER = timedelta(minutes=45)


def when(run):
    return datetime.fromisoformat(run["createdAt"].replace("Z", "+00:00"))


def ago(delta):
    minutes = max(0, int(delta.total_seconds() // 60))
    if minutes < 60:
        return f"{minutes} min ago"
    hours, rest = divmod(minutes, 60)
    return f"{hours} h {rest} min ago"


def main():
    runs = json.load(open(sys.argv[1], encoding="utf-8"))
    now = datetime.now(timezone.utc)
    recent = sorted((r for r in runs if when(r) >= now - WINDOW), key=when)
    done = [r for r in recent if r.get("conclusion")]
    scheduled = [r for r in done if r.get("event") == "schedule"]

    bad = [r for r in done if r.get("conclusion") != "success"]
    latest = done[-1] if done else None

    if latest is None:
        headline = "**No completed runs in 24 hours.** The schedule may be disabled."
    elif bad:
        headline = f"**{len(bad)} of {len(done)} runs failed.**"
    elif now - when(latest) > STALE_AFTER:
        headline = (
            f"**Last attempt {ago(now - when(latest))} — the 15-minute schedule looks stalled.**"
        )
    else:
        headline = (
            f"Running normally — last attempt {ago(now - when(latest))}, "
            f"{len(done)} in 24 hours, no capacity yet."
        )

    print(headline)
    print()
    print("| | |")
    print("|---|---|")
    print(f"| Attempts, last 24 h | {len(done)} ({len(scheduled)} scheduled) |")
    print(f"| Failed runs | {len(bad)} |")
    if latest is not None:
        print(
            f"| Last attempt | {when(latest).strftime('%H:%M UTC')} "
            f"({ago(now - when(latest))}) — {latest.get('conclusion')} |"
        )
        print(f"| Last run log | {latest.get('url')} |")
    if bad:
        print(
            f"| Most recent failure | {when(bad[-1]).strftime('%Y-%m-%d %H:%M UTC')} "
            f"— {bad[-1].get('url')} |"
        )
    print()
    print(
        "Posted at 08:00, 14:00 and 20:00 Saigon. A missing comment means the "
        "status job stopped. A green run means the attempt reached Oracle; "
        "`no capacity` is the normal answer in ap-singapore-1."
    )


if __name__ == "__main__":
    main()
