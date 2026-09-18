import os
import json
from pathlib import Path
from tqdm import tqdm
import shutil

# ---------------- Paths ----------------
INPUT_ROOT = os.environ.get("FC_INPUT_ROOT", "fotocasa_clean_properties_global_deduped")  # Original JSON files
OUTPUT_ROOT = os.environ.get("FC_OUTPUT_ROOT", "mapped_final_urgent")  # New folder for mapped JSONs
LOG_FILE = os.environ.get("FC_LOG_FILE", "logs/mapping_errors_urgent.log")
MAPPING_FILE = os.environ.get("FC_MAPPING_FILE", "manual_map.json")
os.makedirs(OUTPUT_ROOT, exist_ok=True)
os.makedirs("logs", exist_ok=True)

# ---------------- Load Mapping ----------------
with open(MAPPING_FILE, "r", encoding="utf-8") as f:
    MAPPING = json.load(f)

# ---------------- Mapping Helper ----------------
def map_field(item, field, mapping_section):
    """Map a single field to human-readable using mapping JSON"""
    if field not in item or item[field] is None:
        return
    value = item[field]
    # Special case: 'features' is a list of objects with id
    if isinstance(value, list):
        item[f"{field}_str"] = [mapping_section.get(str(v.get("id", v)), v) for v in value]
    # Special case: 'energyCertificate' is a dict with rating & status
    elif field == "energyCertificate" and isinstance(value, dict):
        mapped = {}
        rating = value.get("rating")
        status = value.get("status")
        if rating is not None:
            mapped["rating"] = mapping_section.get("rating", {}).get(rating, rating)
        if status is not None:
            mapped["status"] = mapping_section.get("status", {}).get(str(status), status)
        item[field] = mapped
    else:
        item[f"{field}_str"] = mapping_section.get(str(value), value)

# ---------------- Enrichment ----------------
def map_item(item):
    mapping_fields = [
        "transactionType", "propertyType", "propertySubtype", "purchaseType",
        "conservationStatus", "addressVisibilityMode", "orientation", "floor",
        "antiquity", "hotWater", "heating", "energyCertificate", "features",
        "multimediaType", "agencyType", "floorType"
    ]
    for field in mapping_fields:
        if field in MAPPING:
            map_field(item, field, MAPPING[field])

    # Map multimedia.type inside multimedia array
    if "multimedia" in item and isinstance(item["multimedia"], list):
        for m in item["multimedia"]:
            t = m.get("type")
            if t:
                m["type_str"] = MAPPING.get("multimediaType", {}).get(str(t), t)

    # Map agency.type
    if "agency" in item and "type" in item["agency"]:
        t = item["agency"]["type"]
        item["agency"]["type_str"] = MAPPING.get("agencyType", {}).get(t, t)

    return item

# ---------------- File Processing ----------------
def map_file(input_path):
    input_path = Path(input_path)
    rel_path = input_path.relative_to(INPUT_ROOT)
    output_path = Path(OUTPUT_ROOT) / rel_path
    output_path.parent.mkdir(parents=True, exist_ok=True)

    tmp_file = output_path.with_suffix(".tmp")  # safe write
    try:
        with open(input_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        items = data.get("items", [])
        mapped_items = []
        for item in items:
            try:
                mapped_items.append(map_item(item))
            except Exception as e:
                with open(LOG_FILE, "a", encoding="utf-8") as log:
                    log.write(f"{input_path} --> {str(e)}\n")

        data["items"] = mapped_items

        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        shutil.move(str(tmp_file), str(output_path))  # overwrite safely
    except Exception as e:
        with open(LOG_FILE, "a", encoding="utf-8") as log:
            log.write(f"{input_path} --> {str(e)}\n")

# ---------------- Main ----------------
def main():
    all_files = list(Path(INPUT_ROOT).glob("**/*.json"))
    print(f"Found {len(all_files)} JSON files to map")
    for file in tqdm(all_files):
        map_file(file)

if __name__ == "__main__":
    main()
