import json
import os
from collections import defaultdict
from pathlib import Path

ROOT = "fotocasa_clean_properties_urgent"

if not os.path.exists(ROOT):
    print(f"Directory not found: {ROOT}")
    exit()

thread_sets = defaultdict(set)
thread_page_counts = defaultdict(lambda: defaultdict(int))
global_seen = set()

for dirpath, dirnames, filenames in os.walk(ROOT):
    parts = Path(dirpath).parts
    if len(parts) < 2 or not parts[1].startswith("thread_"):
        continue

    thread_id = parts[1]

    for fn in filenames:
        if not fn.endswith(".json"):
            continue
        filepath = os.path.join(dirpath, fn)

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            print(f"[WARN] Failed to read {filepath}: {e}")
            continue

        items = data.get("items", [])
        count = 0
        for item in items:
            pid = item.get("propertyId")
            if pid:
                thread_sets[thread_id].add(pid)
                global_seen.add(pid)
                count += 1

        # Store per-page count (relative path under the thread dir)
        rel_path = os.path.relpath(filepath, os.path.join(ROOT, thread_id))
        thread_page_counts[thread_id][rel_path] = count

print("=" * 60)
print("UNIQUE propertyIds PER THREAD")
print("=" * 60)
for tid in sorted(thread_sets.keys(), key=lambda x: int(x.split("_")[1])):
    print(f"  {tid}: {len(thread_sets[tid]):>8,} unique propertyIds")

print("=" * 60)
print(f"GLOBAL UNIQUE propertyIds: {len(global_seen):,}")
print("=" * 60)

# Per-page breakdown (can be very long, print only first few per thread as sample)
print("\nSAMPLE per-page counts (first 5 pages per thread):")
for tid in sorted(thread_page_counts.keys(), key=lambda x: int(x.split("_")[1])):
    pages = list(thread_page_counts[tid].items())[:5]
    print(f"\n{tid}:")
    for page_path, count in pages:
        print(f"  {page_path}: {count} items")
