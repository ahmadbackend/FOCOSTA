import ijson
from collections import Counter

file_path = 'merged.json'

print("Streaming JSON file...")
property_ids = []

# Stream the JSON array item by item
with open(file_path, 'rb') as f:
    items = ijson.items(f, 'item')

    for idx, item in enumerate(items, 1):
        property_ids.append(item['propertyId'])

        if idx % 100000 == 0:
            print(f"Processed {idx:,} items...")

print(f"\nTotal items: {len(property_ids):,}")

# Count duplicates
counter = Counter(property_ids)
duplicates = {pid: count for pid, count in counter.items() if count > 1}

print(f"Unique propertyIds: {len(counter):,}")
print(f"Duplicates found: {len(duplicates):,}")

if duplicates:
    print("\nDuplicate propertyIds:")
    for pid, count in sorted(duplicates.items(), key=lambda x: x[1], reverse=True)[:50]:
        print(f"  {pid}: {count} times")

    if len(duplicates) > 50:
        print(f"\n... and {len(duplicates) - 50} more duplicates")
else:
    print("\nNo duplicates found!")