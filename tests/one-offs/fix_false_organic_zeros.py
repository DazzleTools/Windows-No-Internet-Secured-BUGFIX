"""
Fix organicUniqueClones false zeros in NCSI gist.

Removes organicUniqueClones from entries where uniqueClones is missing,
since computing organic from absent data produces misleading zeros.

Usage:
  python fix_false_organic_zeros.py --dry-run    # Preview (default)
  python fix_false_organic_zeros.py --apply       # Write to gist
"""

import argparse
import json
import subprocess
import sys


GIST_ID = "1362078955559665832b72835b309e98"


def gh_api(endpoint):
    result = subprocess.run(
        ["gh", "api", endpoint], capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"Error: {result.stderr}", file=sys.stderr)
        return None
    return json.loads(result.stdout)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", default=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if args.apply:
        args.dry_run = False

    print("Fetching gist state...")
    gist_data = gh_api(f"gists/{GIST_ID}")
    if not gist_data:
        sys.exit(1)

    state = json.loads(gist_data["files"]["state.json"]["content"])

    changes = []
    for entry in state.get("dailyHistory", []):
        date = entry.get("date", "")[:10]
        if "uniqueClones" not in entry and "organicUniqueClones" in entry:
            old = entry["organicUniqueClones"]
            del entry["organicUniqueClones"]
            changes.append(f"  {date}: Removed organicUniqueClones={old}")

    if changes:
        print(f"\n{len(changes)} changes:")
        for c in changes:
            print(c)
    else:
        print("\nNo changes needed.")
        return

    if not args.dry_run:
        print("\nApplying to gist...")
        content = json.dumps(state, indent=2)
        payload = json.dumps({"files": {"state.json": {"content": content}}})
        result = subprocess.run(
            ["gh", "api", f"gists/{GIST_ID}", "-X", "PATCH", "--input", "-"],
            input=payload, capture_output=True, text=True
        )
        if result.returncode == 0:
            print("Gist updated.")
        else:
            print(f"Error: {result.stderr}", file=sys.stderr)
    else:
        print("\n[DRY RUN] Use --apply to write.")


if __name__ == "__main__":
    main()
