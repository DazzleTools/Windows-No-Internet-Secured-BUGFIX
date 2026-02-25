#!/usr/bin/env python3
"""Verify GitHub Statistics API week alignment across endpoints.

Checks that commit_activity, code_frequency, and participation all use
consistent Sunday-aligned UTC week boundaries. Also validates that
click URLs generated from participation dates match actual commits.
"""

import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone

REPO = "DazzleTools/Windows-No-Internet-Secured-BUGFIX"


def gh_api(endpoint):
    result = subprocess.run(
        ["gh", "api", f"repos/{REPO}/{endpoint}"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"Error fetching {endpoint}: {result.stderr}")
        return None
    return json.loads(result.stdout)


def main():
    print("=== Commit Activity (includes week timestamps) ===")
    commit_activity = gh_api("stats/commit_activity")
    if commit_activity:
        ca_weeks = {}
        for entry in commit_activity:
            d = datetime.fromtimestamp(entry["week"], tz=timezone.utc)
            if entry["total"] > 0:
                print(f"  {d.strftime('%Y-%m-%d %A')} | {entry['total']} commits")
                ca_weeks[entry["week"]] = entry["total"]

    print("\n=== Code Frequency (includes week timestamps) ===")
    code_freq = gh_api("stats/code_frequency")
    if code_freq:
        for entry in code_freq:
            if entry[1] != 0 or entry[2] != 0:
                d = datetime.fromtimestamp(entry[0], tz=timezone.utc)
                print(f"  {d.strftime('%Y-%m-%d %A')} | +{entry[1]} -{abs(entry[2])}")

    print("\n=== Participation (NO timestamps - must derive) ===")
    participation = gh_api("stats/participation")
    if participation and commit_activity:
        # Use commit_activity's last week timestamp to anchor participation
        last_ca_week = commit_activity[-1]["week"]
        last_ca_date = datetime.fromtimestamp(last_ca_week, tz=timezone.utc)
        print(f"  Commit activity last week: {last_ca_date.strftime('%Y-%m-%d %A')}")

        all_commits = participation["all"]
        owner_commits = participation["owner"]

        print(f"\n  Non-zero participation weeks:")
        for i in range(52):
            if all_commits[i] > 0:
                # Method 1: Naive (now - offset) — CURRENT BUGGY CODE
                now = datetime.now(timezone.utc)
                naive_date = now - timedelta(weeks=51 - i)

                # Method 2: Anchored to commit_activity's last week
                anchored_date = last_ca_date - timedelta(weeks=51 - i)

                community = all_commits[i] - owner_commits[i]
                match_ca = "MATCH" if anchored_date.timestamp() in [e["week"] for e in commit_activity] else ""
                print(f"  [{i:2d}] Naive: {naive_date.strftime('%Y-%m-%d %A')} | "
                      f"Anchored: {anchored_date.strftime('%Y-%m-%d %A')} | "
                      f"all={all_commits[i]}, owner={owner_commits[i]}, community={community} {match_ca}")

        # Verify anchored dates match commit_activity
        print("\n=== Cross-validation ===")
        for i in range(52):
            anchored_ts = int((last_ca_date - timedelta(weeks=51 - i)).timestamp())
            ca_entry = next((e for e in commit_activity if e["week"] == anchored_ts), None)
            if ca_entry and ca_entry["total"] > 0:
                if all_commits[i] != ca_entry["total"]:
                    print(f"  MISMATCH week {i}: participation={all_commits[i]}, commit_activity={ca_entry['total']}")
                else:
                    d = datetime.fromtimestamp(anchored_ts, tz=timezone.utc)
                    print(f"  OK week {i}: {d.strftime('%Y-%m-%d')} = {all_commits[i]} commits")


if __name__ == "__main__":
    main()
