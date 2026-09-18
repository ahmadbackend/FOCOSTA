import json

# Load both files
with open("missed_agencies_with_phone.json", "r", encoding="utf-8") as f:
    phone_data = json.load(f)

with open("agencies_with_phone_email_urgent.json", "r", encoding="utf-8") as f:
    email_data = json.load(f)

# Create dict for quick lookup by publisher_id
email_dict = {a["publisher_id"]: a for a in email_data}

# Merge
merged_agencies = []
for agency in phone_data:
    pid = agency["publisher_id"]
    if pid in email_dict:
        agency.update({
            "email": email_dict[pid].get("email"),
            "website": email_dict[pid].get("website")
        })
    merged_agencies.append(agency)

# Save merged result
with open("agencies_full_urgent.json", "w", encoding="utf-8") as f:
    json.dump(merged_agencies, f, indent=2, ensure_ascii=False)
