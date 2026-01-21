import json

input_file = "failed_pages.log.log"
output_file = "failed_urls.json"

failed_urls = []

with open(input_file, "r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue

        parts = line.split(",", 3)
        # 0 = id
        # 1 = url
        # 2 = error
        # 3 = timestamp

        if len(parts) >= 2:
            failed_urls.append(parts[1])

with open(output_file, "w", encoding="utf-8") as f:
    json.dump(failed_urls, f, indent=2)

print(f"Saved {len(failed_urls)} failed URLs to {output_file}")
