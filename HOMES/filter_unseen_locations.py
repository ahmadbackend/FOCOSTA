import json
import os

# ---------------- CONFIG ----------------
EXISTING_FILE = os.environ.get("FC_EXISTING_FILE", "fotocasa_locations_urgent.json")
NEW_FILE = os.environ.get("FC_NEW_FILE", "fotocasa_locations_depth3.json")
OUTPUT_FILE = os.environ.get("FC_OUTPUT_FILE", "fotocasa_locations_unseen.json")  # Matching modes (can combine):
MATCH_BY_COMBINED_ID = True    # exact combinedLocationIds match
MATCH_BY_HIERARCHY = True      # small numeric location covered by larger existing one
MATCH_BY_GEO = False           # match by (latitude, longitude) rounded to 4 decimals
MATCH_BY_TEXT = False          # match by text/baseText string
GEO_DECIMALS = int(os.environ.get("FC_GEO_DECIMALS", 4))
def round_coord(value, decimals):
    try:
        return round(float(value), decimals)
    except (TypeError, ValueError):
        return None


def load_locations(path):
    if not os.path.exists(path):
        print(f"[WARN] File not found: {path}")
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def parse_numeric_id(combined_id):
    """Return list of 9 integers if it's a numeric hierarchy ID, else None."""
    try:
        parts = combined_id.split(",")
        if len(parts) != 9:
            return None
        return [int(p) for p in parts]
    except Exception:
        return None


def is_covered_by_hierarchy(new_loc, existing_numeric_ids):
    """Check if new numeric location is inside any existing larger location."""
    new_id = new_loc.get("combinedLocationIds")
    new_parts = parse_numeric_id(new_id)
    if new_parts is None:
        return False

    for existing_parts in existing_numeric_ids:
        covered = True
        for i in range(9):
            if existing_parts[i] != 0 and new_parts[i] != existing_parts[i]:
                covered = False
                break
        if covered:
            return True

    return False


def build_keys(locations):
    """Build sets of keys for matching existing locations."""
    keys = set()
    numeric_ids = []

    for loc in locations:
        if MATCH_BY_COMBINED_ID:
            cid = loc.get("combinedLocationIds")
            if cid:
                keys.add(("cid", cid))

        if MATCH_BY_HIERARCHY:
            parts = parse_numeric_id(loc.get("combinedLocationIds", ""))
            if parts:
                numeric_ids.append(parts)

        if MATCH_BY_GEO:
            lat = round_coord(loc.get("latitude"), GEO_DECIMALS)
            lng = round_coord(loc.get("longitude"), GEO_DECIMALS)
            if lat is not None and lng is not None:
                keys.add(("geo", lat, lng))

        if MATCH_BY_TEXT:
            text = loc.get("text")
            base = loc.get("baseText")
            if text:
                keys.add(("text", text.lower().strip()))
            if base:
                keys.add(("base", base.lower().strip()))

    return keys, numeric_ids


def location_keys(loc):
    """Return all matching keys for a single location."""
    keys = set()
    if MATCH_BY_COMBINED_ID:
        cid = loc.get("combinedLocationIds")
        if cid:
            keys.add(("cid", cid))
    if MATCH_BY_GEO:
        lat = round_coord(loc.get("latitude"), GEO_DECIMALS)
        lng = round_coord(loc.get("longitude"), GEO_DECIMALS)
        if lat is not None and lng is not None:
            keys.add(("geo", lat, lng))
    if MATCH_BY_TEXT:
        text = loc.get("text")
        base = loc.get("baseText")
        if text:
            keys.add(("text", text.lower().strip()))
        if base:
            keys.add(("base", base.lower().strip()))
    return keys


def main():
    existing = load_locations(EXISTING_FILE)
    new_locations = load_locations(NEW_FILE)

    print(f"[INFO] Existing locations: {len(existing)}")
    print(f"[INFO] New depth-3 locations: {len(new_locations)}")

    existing_keys, existing_numeric_ids = build_keys(existing)
    print(f"[INFO] Built {len(existing_keys)} direct matching keys")
    print(f"[INFO] Built {len(existing_numeric_ids)} numeric hierarchy IDs for coverage check")

    unseen = []
    seen = []
    covered_by_hierarchy = 0

    for loc in new_locations:
        loc_keys = location_keys(loc)
        if loc_keys & existing_keys:
            seen.append(loc)
            continue

        if MATCH_BY_HIERARCHY and is_covered_by_hierarchy(loc, existing_numeric_ids):
            seen.append(loc)
            covered_by_hierarchy += 1
            continue

        unseen.append(loc)

    print(f"[INFO] Already seen (direct match): {len(seen) - covered_by_hierarchy}")
    print(f"[INFO] Covered by hierarchy: {covered_by_hierarchy}")
    print(f"[INFO] Total filtered out: {len(seen)}")
    print(f"[INFO] Unseen: {len(unseen)}")

    if unseen:
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(unseen, f, ensure_ascii=False, indent=2)
        print(f"[DONE] Saved {len(unseen)} unseen locations to {OUTPUT_FILE}")
    else:
        print("[DONE] No unseen locations found")


if __name__ == "__main__":
    main()
