import ijson
import json
import os
import re
from collections import defaultdict

INPUT_FILE = os.environ.get("FC_INPUT_FILE", "private_houses.json")
OUTPUT_DIR = os.environ.get("FC_OUTPUT_DIR", "private_by_location")
os.makedirs(OUTPUT_DIR, exist_ok=True)

REMOVE_KEYS = {
    "products",
    "productsScoring",
    "scoring",
    "leadSaturation",
    "contracts"
}

def safe_filename(name):
    name = re.sub(r"[^\w\s-]", "", name)
    return name.strip().replace(" ", "_") or "UNKNOWN"

# Keep file handles open per location (much faster)
files = {}

def get_writer(location):
    if location not in files:
        filename = safe_filename(location) + ".json"
        path = os.path.join(OUTPUT_DIR, filename)
        f = open(path, "w", encoding="utf-8")
        f.write("[\n")
        files[location] = {"file": f, "first": True}
    return files[location]

with open(INPUT_FILE, "rb") as f:
    parser = ijson.items(f, "item")  # stream root array

    for item in parser:
        # remove junk fields
        for k in REMOVE_KEYS:
            item.pop(k, None)

        # group key
        level2 = item.get("location", {}).get("level2Name", "UNKNOWN")

        writer = get_writer(level2)
        out = writer["file"]

        if not writer["first"]:
            out.write(",\n")
        else:
            writer["first"] = False

        json.dump(item, out, ensure_ascii=False)

# close all files properly
for w in files.values():
    w["file"].write("\n]")
    w["file"].close()

print("Streaming split completed.")
