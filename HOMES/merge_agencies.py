import json
import csv
import os
from pathlib import Path

# -----------------------------
# Extract agency info from item
# -----------------------------
def extract_agency_info_from_item(item):
    # try:
    agency = item.get('agency', {})
    if  agency and agency["type"] != "professional":
        return item
    else:
        return None


    #     tracking_phone = item.get('tracking_phone', '')
    #     email = item.get('email', '')
    #     website = item.get('website', '')
    #
    #     # Spanish URL
    #     spanish_url = ''
    #     for url_obj in agency.get('urls', []):
    #         if url_obj.get('language') == 'es_ES':
    #             spanish_url = 'https://www.fotocasa.es' + url_obj.get('value', '')
    #             break
    #
    #     return {
    #         'publisher_id': agency.get('publisherId'),
    #         'name': agency.get('name', ''),
    #         'type': agency.get('type', ''),
    #         'alias': agency.get('alias', ''),
    #         'is_bank': agency.get('isBank', False),
    #         'phone': item.get('phone', ''),
    #         'tracking_phone': tracking_phone,
    #         'email': email,
    #         'website': website,
    #         'url_es': spanish_url
    #     }
    #
    # except Exception as e:
    #     print(f"Error extracting agency: {e}")
    #     return None


# -----------------------------
# Process one JSON file
# -----------------------------
def process_json_file(json_file_path):
    agencies = []

    try:
        with open(json_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if isinstance(data, list):
            for item in data:
                agency_info = extract_agency_info_from_item(item)
                if agency_info:
                    agencies.append(agency_info)
        else:
            agency_info = extract_agency_info_from_item(data)
            if agency_info:
                agencies.append(agency_info)

        return agencies  # items

    except Exception as e:
        print(f"Error processing {json_file_path}: {e}")
        return []


# -----------------------------
# Merge logic for same publisher_id
# -----------------------------
def merge_agencies(existing, new):
    fields = [
        "phone", "tracking_phone", "email",
        "website", "url_es", "name", "alias", "type"
    ]

    for field in fields:
        if not existing.get(field) and new.get(field):
            existing[field] = new[field]

    return existing


# -----------------------------
# Process all files
# -----------------------------
def process_json_folder(folder_path, output_csv):

    # unique_agencies = {}   # publisher_id → merged agency
    # no_id_agencies = []    # agencies with no publisher_id (keep all)

    json_files = list(Path(folder_path).glob('*.json'))

    if not json_files:
        print(f"No JSON files found in {folder_path}")
        return

    print(f"Found {len(json_files)} JSON files...")
    full_agencies=[]
    for idx, json_file in enumerate(json_files, 1):
        agencies = process_json_file(json_file)
        full_agencies.extend(agencies)
    with open("private_houses.json", "w", encoding="utf-8") as f:
        json.dump(full_agencies, f, ensure_ascii=False, indent=2)

    #     for agency in agencies:
    #         publisher_id = agency.get("publisher_id")
    #
    #         # Case 1 — no publisher_id → store duplicates
    #         if not publisher_id:
    #             no_id_agencies.append(agency)
    #             continue
    #
    #         # Case 2 — merge by publisher_id
    #         if publisher_id not in unique_agencies:
    #             unique_agencies[publisher_id] = agency
    #         else:
    #             unique_agencies[publisher_id] = merge_agencies(
    #                 unique_agencies[publisher_id],
    #                 agency
    #             )
    #
    #     if idx % 10 == 0:
    #         print(f"Processed {idx}/{len(json_files)} files...")
    #
    # print(f"\nUnique agencies (with ID): {len(unique_agencies)}")
    # print(f"Agencies without ID (duplicates kept): {len(no_id_agencies)}")
    #
    # # -----------------------------
    # # Write CSV
    # # -----------------------------
    # fieldnames = [
    #     'name', 'type', 'website',
    #     'tracking_phone', 'phone',
    #     'url_es', 'publisher_id',
    #     'alias', 'is_bank', 'email'
    # ]

    # with open(output_csv, 'w', newline='', encoding='utf-8') as csvfile:
    #     writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
    #     writer.writeheader()
    #
    #     # write merged agencies
    #     for agency in unique_agencies.values():
    #         writer.writerow(agency)
    #
    #     # write no-ID agencies (all duplicates)
    #     for agency in no_id_agencies:
    #         writer.writerow(agency)

    print(f"\n✓ CSV created: {output_csv}")


# -----------------------------
# Run
# -----------------------------
if __name__ == "__main__":
    input_folder = "pretty_final"
    output_csv = "agencies_full_final_2222.csv"

    if not os.path.exists(input_folder):
        print(f"Folder not found: {input_folder}")
    else:
        process_json_folder(input_folder, output_csv)
