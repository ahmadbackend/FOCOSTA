import os
import json
from glob import glob

DATA_ROOT = os.path.join(os.path.dirname(__file__), 'enriched_final_urgent')
OUTPUT_FILE = os.path.join(os.path.dirname(__file__), 'unique_agencies_urgent.json')
BASE_URL = 'https://www.fotocasa.es'

unique_agencies = {}

for json_file in glob(os.path.join(DATA_ROOT, '*.json')):
    print(f"Processing file: {json_file}")
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        items = data.get('items', [])

        for item in items:
            agency = item.get('agency')
            if not agency :
                continue
            name = agency.get('name')
            publisher_id = agency.get("publisherId", "")
            agency_type = agency.get("type", "")
            for url_obj in agency['urls']:
                if url_obj.get('language') == 'es_ES':
                    abs_path = BASE_URL + url_obj['value']
                    unique_agencies[name] = {
                        "url": abs_path,
                        "publisher_id": publisher_id,
                        "type": agency_type
                    }
    except Exception as e:
        print(f"Error processing file {json_file}: {e}")
        # Optionally log or print errors for malformed files
        pass

result = [
    {
        "agency name": name,
        "agency_abs_path": data["url"],
        "publisher_id": data["publisher_id"],
        "type": data["type"]
    }
    for name, data in unique_agencies.items()
]

with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
    json.dump(result, f, ensure_ascii=False, indent=2)

print(f"Extracted {len(result)} unique agencies. Output written to {OUTPUT_FILE}")
