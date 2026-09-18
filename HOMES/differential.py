import json

FILE_A = "unique_2_agencies.json"
FILE_B = "unique_missed_agencies.json"
OUTPUT = "missing_from_b.json"

def load(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

a = load(FILE_A)
b = load(FILE_B)

# Build fast lookup set from B
b_ids = {x["publisher_id"] for x in b}

# Keep only items from A that are not in B
diff = [x for x in a if x["publisher_id"] not in b_ids]

print(f"A count: {len(a)}")
print(f"B count: {len(b)}")
print(f"A - B count: {len(diff)}")

# Save result
with open(OUTPUT, "w", encoding="utf-8") as f:
    json.dump(diff, f, indent=2, ensure_ascii=False)

print(f"Saved to {OUTPUT}")
