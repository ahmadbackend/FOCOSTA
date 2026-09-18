import os
import json
import re
import unicodedata
from pathlib import Path
from textblob import TextBlob
from tqdm import tqdm

# ---------------- Paths ----------------
INPUT_ROOT = os.environ.get("FC_INPUT_ROOT", "particular_properties_urgent")
OUTPUT_ROOT = os.environ.get("FC_OUTPUT_ROOT", "enriched_final_urgent")
LOG_FILE = os.environ.get("FC_LOG_FILE", "logs/enrich_errors_urgent.log")
os.makedirs(OUTPUT_ROOT, exist_ok=True)
os.makedirs("logs", exist_ok=True)

# ---------------- Normalization ----------------
def normalize(text):
    text = unicodedata.normalize("NFKD", text)
    text = text.lower()
    return text

# ---------------- Feature Extractors ----------------
def extract_features(text):
    features = {}
    text = normalize(text)

    # Area
    m = re.search(r"(\d+)\s*m²", text)
    if m:
        features["area_m2"] = int(m.group(1))

    # Bedrooms
    m = re.search(r"(\d+)\s+habitaciones?", text)
    if m:
        features["bedrooms"] = int(m.group(1))

    # Floor
    floors = {
        "primera": 1,
        "segunda": 2,
        "tercera": 3,
        "cuarta": 4,
        "quinta": 5,
        "sexta": 6
    }
    for k, v in floors.items():
        if k in text:
            features["floor"] = v

    # Elevator
    features["elevator"] = not ("sin ascensor" in text)

    # Attic
    features["has_attic"] = "buhardilla" in text

    # Extras
    features["near_transport"] = "transporte" in text
    features["near_green_area"] = "zonas verdes" in text
    features["near_schools"] = "colegios" in text
    features["extra_costs"] = "no incluye impuestos" in text

    # Sentiment
    #     features["sentiment"] = 0

    return features

# ---------------- Location Extractor ----------------
def extract_location(title):
    # Split by comma to separate main location parts
    try:
        parts = title.split(",")
        if len(parts) >= 2:
            street = parts[0].strip()
            neighbourhood = parts[1].strip()
            city = parts[-1].strip()
        else:
            street = title
            neighbourhood = ""
            city = ""
        return {
            "street": street,
            "neighbourhood": neighbourhood,
            "city": city
        }
    except:
        return {}

# ---------------- Enrichment ----------------
def enrich_item(item):
    desc = item.get("description", "")
    title = desc.split(",")[0]
    features = extract_features(desc)
    #location = extract_location(title)
    item["title"]=title

    item["features_2"] = {**features}
    return item

def enrich_file(input_path, output_path):
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    items = data.get("items", [])
    enriched_items = []

    for item in items:
        try:
            enriched_item = enrich_item(item)
            enriched_items.append(enriched_item)
        except Exception as e:
            with open(LOG_FILE, "a", encoding="utf-8") as log:
                log.write(f"{input_path} --> {str(e)}\n")

    # Save back enriched JSON (keep original structure)
    data["items"] = enriched_items

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ---------------- Main ----------------
def main():
    all_files = []
    for root, dirs, files in os.walk(INPUT_ROOT):
        for f in files:
            if f.endswith(".json"):
                all_files.append(Path(root) / f)

    print(f"Found {len(all_files)} files")

    for file in tqdm(all_files):
        rel_path = file.relative_to(INPUT_ROOT)
        out_file = Path(OUTPUT_ROOT) / rel_path

        # Skip already enriched files
        if out_file.exists():
            continue

        try:
            enrich_file(file, out_file)
        except Exception as e:
            with open(LOG_FILE, "a", encoding="utf-8") as log:
                log.write(f"{file} --> {str(e)}\n")

if __name__ == "__main__":
    main()
