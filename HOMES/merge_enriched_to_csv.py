import csv
import json
import os
from pathlib import Path

# ---------------- CONFIG ----------------
INPUT_ROOT = os.environ.get("FC_INPUT_ROOT", "enriched_final_urgent")  # folder with batch JSON files
OUTPUT_JSON = os.environ.get("FC_OUTPUT_JSON", "enriched_final_urgent_merged.json")  # single merged JSON
OUTPUT_CSV = os.environ.get("FC_OUTPUT_CSV", "enriched_final_urgent_merged.csv")  # flattened CSV


def iter_items():
    """Yield items from every batch file, one at a time."""
    files = sorted(Path(INPUT_ROOT).glob("*.json"))
    print(f"[INFO] Found {len(files)} input files in {INPUT_ROOT}")
    for path in files:
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            print(f"[ERROR] {path}: {e}")
            continue
        for item in data.get("items", []):
            yield item


def flatten(item, prefix=""):
    """Flatten nested dicts into 'parent_child' columns.
    Lists are stored as JSON strings."""
    row = {}
    for key, value in item.items():
        col = f"{prefix}{key}" if not prefix else f"{prefix}_{key}"
        if isinstance(value, dict):
            row.update(flatten(value, col))
        elif isinstance(value, list):
            row[col] = json.dumps(value, ensure_ascii=False)
        else:
            row[col] = value
    return row


def main():
    # -------- Pass 1: merged JSON (streamed) + collect CSV columns --------
    columns = []
    seen_cols = set()
    total = 0

    with open(OUTPUT_JSON, "w", encoding="utf-8") as out:
        out.write('{"items":[')
        first = True
        for item in iter_items():
            if not first:
                out.write(",")
            out.write(json.dumps(item, ensure_ascii=False))
            first = False
            total += 1

            for col in flatten(item):
                if col not in seen_cols:
                    seen_cols.add(col)
                    columns.append(col)

            if total % 5000 == 0:
                print(f"[MERGE] {total} items...")
        out.write("]}")

    print(f"[OK] Merged {total} items -> {OUTPUT_JSON}")
    print(f"[INFO] {len(columns)} CSV columns")

    # -------- Pass 2: flattened CSV (streamed) --------
    with open(OUTPUT_CSV, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        count = 0
        for item in iter_items():
            writer.writerow(flatten(item))
            count += 1
            if count % 5000 == 0:
                print(f"[CSV] {count} rows...")

    print(f"\n[DONE] {total} items -> {OUTPUT_JSON}, {count} rows -> {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
