import json
import os
from pathlib import Path

# ---------------- CONFIG ----------------
INPUT_ROOT = os.environ.get("FC_INPUT_ROOT", "mapped_final_urgent")  # mapped JSON batch files
OUTPUT_ROOT = os.environ.get("FC_OUTPUT_ROOT", "particular_properties_urgent")  # new folder for particular-only batches
BATCH_SIZE = int(os.environ.get("FC_BATCH_SIZE", 1000))  # items per output batch file

os.makedirs(OUTPUT_ROOT, exist_ok=True)


def is_particular(item):
    agency = item.get("agency") or {}
    return agency.get("type") == "particular"


def save_batch(buffer, batch_num):
    out_file = os.path.join(OUTPUT_ROOT, f"batch_{batch_num:04d}.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump({"items": buffer}, f, ensure_ascii=False)
    print(f"[BATCH] {out_file} -> {len(buffer)} items")


def main():
    input_files = sorted(Path(INPUT_ROOT).glob("*.json"))
    print(f"[INFO] Found {len(input_files)} input files in {INPUT_ROOT}")

    buffer = []
    batch_num = 1
    total_items = 0
    total_particular = 0

    for path in input_files:
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            print(f"[ERROR] {path}: {e}")
            continue

        items = data.get("items", [])
        total_items += len(items)

        for item in items:
            if is_particular(item):
                buffer.append(item)
                total_particular += 1
                if len(buffer) >= BATCH_SIZE:
                    save_batch(buffer, batch_num)
                    batch_num += 1
                    buffer = []

        print(f"[SCAN] {path.name}: {len(items)} items, "
              f"{total_particular} particular so far")

    # Flush remaining items
    if buffer:
        save_batch(buffer, batch_num)
    else:
        batch_num -= 1  # no partial batch written

    print(f"\n✅ DONE — scanned {total_items} items, "
          f"extracted {total_particular} particular "
          f"into {max(batch_num, 0)} batch file(s) in {OUTPUT_ROOT}/")


if __name__ == "__main__":
    main()
