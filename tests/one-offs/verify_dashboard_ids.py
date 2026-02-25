"""
Verify all JS-referenced element IDs exist in the dashboard HTML.

Catches bugs where setText('some-id', ...) or getElementById('some-id')
references an ID that doesn't exist in the HTML markup.

Usage:
    python tests/one-offs/verify_dashboard_ids.py
"""

import re
import sys
from pathlib import Path

def verify_dashboard_ids(html_path=None):
    if html_path is None:
        html_path = Path(__file__).resolve().parents[2] / "docs" / "stats" / "index.html"

    if not html_path.exists():
        print(f"ERROR: Dashboard not found at {html_path}")
        return False

    content = html_path.read_text(encoding="utf-8")

    # Find all setText('id', ...) calls
    set_text_ids = set(re.findall(r"setText\('([^']+)'", content))

    # Find all getElementById('id') calls
    get_elem_ids = set(re.findall(r"getElementById\('([^']+)'", content))

    # Find all id= in HTML
    html_ids = set(re.findall(r'id="([^"]+)"', content))

    # Combined JS references
    all_js_ids = set_text_ids | get_elem_ids
    missing = all_js_ids - html_ids

    if missing:
        print(f"FAIL: {len(missing)} JS-referenced IDs not found in HTML:")
        for m in sorted(missing):
            # Find which JS function references it
            sources = []
            if m in set_text_ids:
                sources.append("setText")
            if m in get_elem_ids:
                sources.append("getElementById")
            print(f"  - {m}  (via {', '.join(sources)})")
        return False

    print(f"PASS: All {len(all_js_ids)} JS-referenced IDs found in HTML.")

    # Also check for duplicate IDs in HTML
    all_id_matches = re.findall(r'id="([^"]+)"', content)
    seen = {}
    duplicates = []
    for id_val in all_id_matches:
        if id_val in seen:
            duplicates.append(id_val)
        seen[id_val] = seen.get(id_val, 0) + 1

    if duplicates:
        print(f"\nWARNING: {len(duplicates)} duplicate IDs found:")
        for d in sorted(set(duplicates)):
            print(f"  - {d} (appears {seen[d]} times)")
    else:
        print(f"PASS: No duplicate IDs found ({len(html_ids)} unique IDs).")

    return len(missing) == 0


if __name__ == "__main__":
    success = verify_dashboard_ids()
    sys.exit(0 if success else 1)
