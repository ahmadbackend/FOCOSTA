import json
import glob
import os

# Load merged agency data
INPUT_ROOT = os.environ.get("FC_INPUT_ROOT", "enriched_final_urgent")
OUTPUT_ROOT = os.environ.get("FC_OUTPUT_ROOT", "full_enriched_mapped_urgent")
with open("agencies_full_urgent.json", "r", encoding="utf-8") as f:
    agencies = json.load(f)

agency_dict = {a["publisher_id"]: a for a in agencies}

# Process all mapped JSON files
for file_path in glob.glob("enriched_final_urgent/*/*.json"):

    with open(file_path, "r", encoding="utf-8") as f:
        properties = json.load(f)

    properties = properties["items"]  # <-- THIS LINE

    # Enrich each property
    #print(file_path, type(properties), "are we here")

    for prop in properties:

        pid = prop.get("agency", {}).get("publisherId")
        if pid and pid in agency_dict:
            agency_info = agency_dict[pid]
            prop.update({
                "tracking_phone": agency_info.get("tracking_phone"),
                "email": agency_info.get("email"),
                "website": agency_info.get("website")
            })

    # Save back (or to a new folder)
    # build mirrored output path
    rel_path = os.path.relpath(file_path, INPUT_ROOT)
    out_file = os.path.join(OUTPUT_ROOT, rel_path)

    os.makedirs(os.path.dirname(out_file), exist_ok=True)

    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(properties, f, indent=2, ensure_ascii=False)

    print(f"Enriched {file_path} -> {out_file}")