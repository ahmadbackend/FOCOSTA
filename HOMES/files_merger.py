import json
import os

ROOT_FOLDER = os.environ.get("FC_ROOT_FOLDER", "full_enriched_mapped")  # main folder
OUTPUT_FILE = os.environ.get("FC_OUTPUT_FILE", "full_merged.json")
all_data = []

for root, dirs, files in os.walk(ROOT_FOLDER):
    for file in files:
        if file.endswith(".json"):
            path = os.path.join(root, file)
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    all_data.extend(data)
                else:
                    all_data.append(data)

with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(all_data, f, indent=2, ensure_ascii=False)

print("Merged", len(all_data), "records into", OUTPUT_FILE)
