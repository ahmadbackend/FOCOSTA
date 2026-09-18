import json
import os
import glob

# ---------- CONFIG ----------
ROOT_FOLDER = os.environ.get("FC_ROOT_FOLDER", "missed_properties_mt")  # your root folder with all worker folders
OUTPUT_FOLDER = os.environ.get("FC_OUTPUT_FOLDER", "deduplicated_properties")
MERGE_SINGLE_FILE = True               # set True if you want 1 big JSON at the end

os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# ---------- TRACK SEEN PROPERTY IDS ----------
seen_ids = set()
merged_data = []

# ---------- WALK THROUGH ALL JSON FILES ----------
json_files = glob.glob(os.path.join(ROOT_FOLDER, "**", "*.json"), recursive=True)
print(f"[INFO] Found {len(json_files)} JSON files to process")

for file_path in json_files:
    with open(file_path, encoding="utf-8") as f:
        try:
            data = json.load(f)
        except Exception as e:
            print(f"[WARN] Failed to load {file_path}: {e}")
            continue

    items = data.get("items", [])
    deduped_items = []

    for item in items:
        pid = item.get("propertyId")
        if pid and pid not in seen_ids:
            seen_ids.add(pid)
            deduped_items.append(item)
            if MERGE_SINGLE_FILE:
                merged_data.append(item)

    # ---------- SAVE DEDUPED FILE ----------
    if not MERGE_SINGLE_FILE:
        # Keep folder structure
        rel_path = os.path.relpath(file_path, ROOT_FOLDER)
        out_file = os.path.join(OUTPUT_FOLDER, rel_path)
        os.makedirs(os.path.dirname(out_file), exist_ok=True)
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump({"items": deduped_items}, f, ensure_ascii=False, indent=2)

print(f"[DONE] Deduplication completed. Total unique properties: {len(seen_ids)}")

# ---------- SAVE SINGLE MERGED FILE ----------
if MERGE_SINGLE_FILE:
    merged_file = os.path.join(OUTPUT_FOLDER, "fotocasa_deduplicated.json")
    with open(merged_file, "w", encoding="utf-8") as f:
        json.dump({"items": merged_data}, f, ensure_ascii=False, indent=2)
    print(f"[INFO] Merged deduplicated file saved: {merged_file}")
