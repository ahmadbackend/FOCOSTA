import json
import os
import shutil
from pathlib import Path

# Optional fast JSON library
try:
    import orjson
    HAS_ORJSON = True
except Exception:
    HAS_ORJSON = False

# ---------------- CONFIG ----------------
INPUT_ROOTS = [
    "fotocasa_clean_properties_urgent",
    "fotocasa_clean_properties_urgent_2",
]
OUTPUT_ROOT = os.environ.get("FC_OUTPUT_ROOT", "fotocasa_clean_properties_global_deduped")
BATCH_SIZE = int(os.environ.get("FC_BATCH_SIZE", 5000))  # properties per output file
LOG_INTERVAL = int(os.environ.get("FC_LOG_INTERVAL", 1000))  # files
LOG_FILE = os.environ.get("FC_LOG_FILE", "logs/global_dedupe.log")
SUMMARY_FILE = os.environ.get("FC_SUMMARY_FILE", "dedupe_summary.json")
os.makedirs("logs", exist_ok=True)
os.makedirs(OUTPUT_ROOT, exist_ok=True)


def log(msg):
    print(msg)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(msg + "\n")


def load_json(path):
    if HAS_ORJSON:
        with open(path, "rb") as f:
            return orjson.loads(f.read())
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def dump_json(obj, path):
    if HAS_ORJSON:
        with open(path, "wb") as f:
            f.write(orjson.dumps(obj))
    else:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))


def collect_all_files(roots):
    all_files = []
    for root in roots:
        if not os.path.exists(root):
            log(f"[WARN] Input directory not found: {root}")
            continue
        for path in Path(root).rglob("page_*.json"):
            all_files.append(path)
    return all_files


def deduplicate_files(files, output_root, batch_size):
    """Single-pass global deduplication using an in-memory seen set."""
    seen_ids = set()
    current_batch = []
    batch_num = 1
    total_written = 0
    total_skipped = 0
    files_processed = 0

    for idx, path in enumerate(files, 1):
        try:
            data = load_json(path)
        except Exception as e:
            log(f"[WARN] Failed to read {path}: {e}")
            continue

        for item in data.get("items", []):
            pid = item.get("propertyId")
            if not pid:
                continue

            if pid in seen_ids:
                total_skipped += 1
                continue

            seen_ids.add(pid)
            current_batch.append(item)

            if len(current_batch) >= batch_size:
                out_path = os.path.join(output_root, f"batch_{batch_num:04d}.json")
                dump_json({"items": current_batch}, out_path)
                total_written += len(current_batch)
                log(f"[WRITE] {out_path} ({len(current_batch)} items)")
                current_batch = []
                batch_num += 1

        files_processed = idx
        if idx % LOG_INTERVAL == 0:
            log(f"[PASS] {idx}/{len(files)} files processed, {total_written} unique written, {len(seen_ids)} distinct IDs")

    if current_batch:
        out_path = os.path.join(output_root, f"batch_{batch_num:04d}.json")
        dump_json({"items": current_batch}, out_path)
        total_written += len(current_batch)
        log(f"[WRITE] final {out_path} ({len(current_batch)} items)")

    return {
        "files_processed": files_processed,
        "total_unique": total_written,
        "total_duplicates_skipped": total_skipped,
        "total_distinct_ids": len(seen_ids),
    }


def main():
    # Clean old output
    if os.path.exists(OUTPUT_ROOT):
        shutil.rmtree(OUTPUT_ROOT)
    os.makedirs(OUTPUT_ROOT, exist_ok=True)

    all_files = collect_all_files(INPUT_ROOTS)
    log(f"[INFO] Found {len(all_files)} page files across {len(INPUT_ROOTS)} input roots")

    if not all_files:
        log("[ERROR] No files found")
        return

    stats = deduplicate_files(all_files, OUTPUT_ROOT, BATCH_SIZE)

    with open(SUMMARY_FILE, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

    log(f"[DONE] Files processed: {stats['files_processed']}")
    log(f"[DONE] Total unique properties written: {stats['total_unique']}")
    log(f"[DONE] Total duplicate properties skipped: {stats['total_duplicates_skipped']}")
    log(f"[DONE] Global deduplication complete. Output: {OUTPUT_ROOT}")


if __name__ == "__main__":
    main()
