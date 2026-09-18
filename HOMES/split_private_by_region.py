import json
import os
import re
from collections import defaultdict

# ---------------- CONFIG ----------------
INPUT_FILE = os.environ.get("FC_INPUT_FILE", "enriched_final_urgent_merged.json")  # merged JSON from merge_enriched_to_csv.py
OUTPUT_DIR = os.environ.get("FC_OUTPUT_DIR", "private_urgent_by_region")  # one JSON file per region
REGION_FIELD = os.environ.get("FC_REGION_FIELD", "level2Name")  # province (matches private_by_location)
ONLY_PARTICULAR = True                               # keep only private sellers

os.makedirs(OUTPUT_DIR, exist_ok=True)


def safe_filename(name):
    """'Araba / Álava' -> 'Araba_-_Álava' (spaces -> underscores)."""
    name = name.strip()
    name = re.sub(r"\s+", " ", name)      # collapse whitespace
    return name.replace(" ", "_")


def main():
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        items = json.load(f).get("items", [])
    print(f"[INFO] Loaded {len(items)} items from {INPUT_FILE}")

    by_region = defaultdict(list)
    skipped_not_particular = 0
    skipped_no_region = 0

    for item in items:
        # if ONLY_PARTICULAR and (item.get("agency") or {}).get("type") != "particular":
        #     skipped_not_particular += 1
        #     continue

        region = (item.get("location") or {}).get(REGION_FIELD)
        if not region:
            skipped_no_region += 1
            region = "_unknown"

        by_region[region].append(item)

    total_written = 0
    for region in sorted(by_region):
        region_items = by_region[region]
        out_file = os.path.join(OUTPUT_DIR, safe_filename(region) + ".json")
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(region_items, f, ensure_ascii=False, indent=2)
        total_written += len(region_items)
        print(f"[REGION] {region}: {len(region_items)} items -> {out_file}")

    print(f"\n[DONE] {total_written} items in {len(by_region)} region file(s) under {OUTPUT_DIR}/")
    # print(f"[SKIP] not particular: {skipped_not_particular}, no region: {skipped_no_region}")


if __name__ == "__main__":
    main()
