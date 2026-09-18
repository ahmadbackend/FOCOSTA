import os
import ijson
import csv

INPUT_FILE = os.environ.get("FC_INPUT_FILE", "merged.json")  # your 3GB JSON
OUTPUT_FILE = os.environ.get("FC_OUTPUT_FILE", "agencies_full_data.csv")
BASE_URL = "https://www.fotocasa.es/es"

seen_publishers = set()

with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f_out:
    writer = csv.writer(f_out)

    writer.writerow([
        "name",
        "type",
        "website",
        "tracking_phone",
        "phone",
        "email",
        "url",
        "publisher_id",
        "alias",
        "is_bank"
    ])

    with open(INPUT_FILE, "rb") as f:
        # If your JSON is a big list → use "item"
        # If wrapped inside { "items": [ ... ] } → use "items.item"
        parser = ijson.items(f, "item")

        for obj in parser:
            agency = obj.get("agency")
            if not agency:
                continue

            publisher_id = agency.get("publisherId")
            if not publisher_id:
                continue

            # deduplicate agencies
            if publisher_id in seen_publishers:
                continue
            seen_publishers.add(publisher_id)

            # ---- extract ES url ----
            es_url = ""
            for u in agency.get("urls", []):
                if u.get("language") == "es_ES":
                    es_url = BASE_URL + u.get("value", "")
                    break

            writer.writerow([
                agency.get("name", ""),
                agency.get("type", ""),
                obj.get("website", ""),
                obj.get("tracking_phone", ""),
                obj.get("phone", ""),
                obj.get("email", ""),
                es_url,
                publisher_id,
                agency.get("alias", ""),
                agency.get("isBank", False)
            ])

print("Done. CSV written:", OUTPUT_FILE)
