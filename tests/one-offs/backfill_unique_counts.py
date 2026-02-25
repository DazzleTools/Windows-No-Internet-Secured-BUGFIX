"""
One-time backfill of uniqueClones and uniqueViews into gist state.json.

Fetches the 14-day traffic data from GitHub API (which includes uniques),
then patches existing dailyHistory entries and sets cumulative totals.

Usage:
    python tests/one-offs/backfill_unique_counts.py [--dry-run]
"""

import json
import subprocess
import sys

GIST_ID = "1362078955559665832b72835b309e98"
OWNER = "DazzleTools"
REPO = "Windows-No-Internet-Secured-BUGFIX"

def run_gh(args):
    result = subprocess.run(["gh"] + args, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"ERROR: gh {' '.join(args)}\n{result.stderr}")
        sys.exit(1)
    return result.stdout.strip()

def main():
    dry_run = "--dry-run" in sys.argv

    # 1. Fetch current state from gist
    print("Fetching gist state.json...")
    state_raw = run_gh(["api", f"gists/{GIST_ID}", "--jq", '.files["state.json"].content'])
    state = json.loads(state_raw)

    # 2. Fetch 14-day clone data with uniques
    print("Fetching clone traffic...")
    clones_raw = run_gh(["api", f"repos/{OWNER}/{REPO}/traffic/clones?per=day"])
    clones_data = json.loads(clones_raw)

    # 3. Fetch 14-day view data with uniques
    print("Fetching view traffic...")
    views_raw = run_gh(["api", f"repos/{OWNER}/{REPO}/traffic/views?per=day"])
    views_data = json.loads(views_raw)

    # 4. Build lookup maps: date -> uniques
    clone_uniques = {}
    for day in clones_data.get("clones", []):
        date_key = day["timestamp"][:10]
        clone_uniques[date_key] = day["uniques"]

    view_uniques = {}
    for day in views_data.get("views", []):
        date_key = day["timestamp"][:10]
        view_uniques[date_key] = day["uniques"]

    print(f"  Clone uniques: {len(clone_uniques)} days, total {sum(clone_uniques.values())}")
    print(f"  View uniques:  {len(view_uniques)} days, total {sum(view_uniques.values())}")

    # 5. Patch dailyHistory entries
    patched = 0
    history = state.get("dailyHistory", [])
    for entry in history:
        date_key = entry.get("date", "")[:10]
        changed = False

        if date_key in clone_uniques and entry.get("uniqueClones") in (None, 0):
            entry["uniqueClones"] = clone_uniques[date_key]
            changed = True

        if date_key in view_uniques and entry.get("uniqueViews") in (None, 0):
            entry["uniqueViews"] = view_uniques[date_key]
            changed = True

        if changed:
            patched += 1
            print(f"  Patched {date_key}: uniqueClones={entry.get('uniqueClones', 0)}, uniqueViews={entry.get('uniqueViews', 0)}")

    # 6. Set cumulative totals from the 14-day window
    total_unique_clones = sum(clone_uniques.values())
    total_unique_views = sum(view_uniques.values())

    old_uc = state.get("totalUniqueClones", 0)
    old_uv = state.get("totalUniqueViews", 0)
    state["totalUniqueClones"] = total_unique_clones
    state["totalUniqueViews"] = total_unique_views

    print(f"\nSummary:")
    print(f"  dailyHistory entries patched: {patched}/{len(history)}")
    print(f"  totalUniqueClones: {old_uc} -> {total_unique_clones}")
    print(f"  totalUniqueViews:  {old_uv} -> {total_unique_views}")

    if dry_run:
        print("\n[DRY RUN] No changes written to gist.")
        return

    # 7. Write back to gist
    print("\nUpdating gist...")
    payload = {"files": {"state.json": {"content": json.dumps(state)}}}
    payload_path = "tests/one-offs/_backfill_payload.json"
    with open(payload_path, "w") as f:
        json.dump(payload, f)

    updated_at = run_gh(["api", "--method", "PATCH", f"gists/{GIST_ID}",
                         "--input", payload_path, "--jq", ".updated_at"])
    print(f"Gist updated at {updated_at}")

    # Cleanup
    import os
    os.remove(payload_path)
    print("Done.")


if __name__ == "__main__":
    main()
