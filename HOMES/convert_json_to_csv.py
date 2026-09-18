import json
import csv
import os
from pathlib import Path

# ----------------------------------
# Keep only properties with
# agency.type == "particular"
# ----------------------------------
def is_private_house(item):
    agency = item.get("agency")
    return isinstance(agency, dict) and agency.get("type") == "particular"


# ----------------------------------
# Recursive JSON flattener
# ----------------------------------
def flatten_json(obj, parent_key="", sep="_"):
    items = {}

    if isinstance(obj, dict):
        for k, v in obj.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            items.update(flatten_json(v, new_key, sep))

    elif isinstance(obj, list):
        # Convert lists to JSON strings to preserve data
        items[parent_key] = json.dumps(obj, ensure_ascii=False)

    else:
        items[parent_key] = obj

    return items


# ----------------------------------
# Flatten one property for CSV
# ----------------------------------
def flatten_property(item):
    return flatten_json(item)


# ----------------------------------
# Process all JSON files in folder
# ----------------------------------
def process_json_folder(folder_path):
    all_properties = []

    json_files = list(Path(folder_path).glob("*.json"))
    print(f"Found {len(json_files)} JSON files")

    for idx, json_file in enumerate(json_files, 1):
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            if isinstance(data, list):
                for item in data:
                    if is_private_house(item):
                        all_properties.append(item)
            else:
                if is_private_house(data):
                    all_properties.append(data)

            if idx % 10 == 0:
                print(f"Processed {idx}/{len(json_files)} files")

        except Exception as e:
            print(f"Error reading {json_file}: {e}")

    return all_properties


# ----------------------------------
# MAIN
# ----------------------------------
if __name__ == "__main__":

    input_folder = "private_pretty_final"
    json_output = "private_houses_3.json"
    csv_output = "private_houses_3.csv"

    if not os.path.exists(input_folder):
        print("Folder not found:", input_folder)
        exit()

    # 1) Collect all private houses
    properties = process_json_folder(input_folder)
    print("Private houses found:", len(properties))

    # 2) Save raw JSON (lossless)
    with open(json_output, "w", encoding="utf-8") as f:
        json.dump(properties, f, ensure_ascii=False, indent=2)

    print("Saved:", json_output)

    # 3) Flatten everything for CSV
    flat_rows = [flatten_property(p) for p in properties]

    # 4) Build CSV headers from all flattened keys
    fieldnames = set()
    for row in flat_rows:
        fieldnames.update(row.keys())
    fieldnames = sorted(fieldnames)

    # 5) Write CSV
    with open(csv_output, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in flat_rows:
            writer.writerow(row)

    print("CSV rows written:", len(flat_rows))
    print("Saved:", csv_output)
