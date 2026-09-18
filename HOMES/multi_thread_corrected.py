import json
import math
import os
import signal
import sys
import threading
import time
from pathlib import Path
from curl_cffi import requests

from proxy_rotator import ProxyRotator

# ---------------- CONFIG ----------------
BASE_URL = "https://web.gw.fotocasa.es/v1/search/ads"
LOCATIONS_FILE = os.environ.get("FC_LOCATIONS_FILE", "fotocasa_locations_unseen.json")  # generated from suggest API
OUTPUT_ROOT = os.environ.get("FC_OUTPUT_ROOT", "fotocasa_clean_properties_urgent_2")
LOG_FILE_PREFIX = os.environ.get("FC_LOG_FILE_PREFIX", "failed_requests_urgent_2")
PROXY_FILE = os.environ.get("FC_PROXY_FILE", "decodo_scraper_ips.txt")
NUM_THREADS = int(os.environ.get("FC_NUM_THREADS", 30))
PAGE_SIZE = int(os.environ.get("FC_PAGE_SIZE", 30))
SLEEP = float(os.environ.get("FC_SLEEP", 0.4))
MAX_DUPLICATE_HITS = int(os.environ.get("FC_MAX_DUPLICATE_HITS", 100))  # stop location after this many duplicate pages
SKIP_LOCATIONS = {"724,0,0,0,0,0,0,0,0"}  # skip country-wide Spain (redundant with provinces)
SKIP_ZERO_ADS = True       # skip locations with adsCount == 0 (no retrievable ads)

COMPLETED_MARKER = os.environ.get("FC_COMPLETED_MARKER", "_completed.json")
LOCATION_STATE_FILE = os.environ.get("FC_LOCATION_STATE_FILE", "_location_state.json")  # Global shutdown event for graceful CTRL+C / SIGTERM handling
shutdown_event = threading.Event()


def signal_handler(signum, frame):
    print("\n[SHUTDOWN] Stop requested. Finishing current pages, please wait...")
    shutdown_event.set()


# Register signal handlers
signal.signal(signal.SIGINT, signal_handler)
try:
    signal.signal(signal.SIGTERM, signal_handler)
except AttributeError:
    pass  # Windows doesn't have SIGTERM

# ---------------- HEADERS ----------------
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/115.0.5790.170 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json",
    "Referer": "https://www.fotocasa.es/",
    "Origin": "https://www.fotocasa.es",
}

# ---------------- HELPERS ----------------
def log_error(log_file, location_id, page, error):
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps({
            "location": location_id,
            "page": page,
            "error": str(error)
        }) + "\n")


def load_property_ids_from_file(path):
    """Return set of propertyIds from a saved page file."""
    ids = set()
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for it in data.get("items", []):
            pid = it.get("propertyId")
            if pid:
                ids.add(pid)
    except Exception:
        pass
    return ids


def load_thread_seen(output_dir):
    """Restore per-thread seen set from all previously saved files."""
    seen = set()
    if not os.path.exists(output_dir):
        return seen

    json_files = list(Path(output_dir).rglob("page_*.json"))
    print(f"[THREAD] Restoring seen set from {len(json_files)} existing files...")

    for i, path in enumerate(json_files):
        if i > 0 and i % 100 == 0 and shutdown_event.is_set():
            print(f"[THREAD] ⚠ Shutdown requested during restore, stopping early")
            return seen
        seen.update(load_property_ids_from_file(path))

    print(f"[THREAD] Restored {len(seen)} seen propertyIds")
    return seen


def is_location_completed(location_dir):
    return os.path.exists(os.path.join(location_dir, COMPLETED_MARKER))


def mark_location_completed(location_dir, combined, total_pulled):
    path = os.path.join(location_dir, COMPLETED_MARKER)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({
            "combinedLocationIds": combined,
            "total_pulled": total_pulled,
            "completed_at": time.strftime("%Y-%m-%dT%H:%M:%S")
        }, f, ensure_ascii=False, indent=2)


def save_location_state(location_dir, combined, last_page, duplicate_pages, total_pulled):
    path = os.path.join(location_dir, LOCATION_STATE_FILE)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({
            "combinedLocationIds": combined,
            "last_page": last_page,
            "duplicate_pages": duplicate_pages,
            "total_pulled": total_pulled,
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S")
        }, f, ensure_ascii=False, indent=2)


def load_location_state(location_dir):
    """Return (local_seen_set, max_saved_page, duplicate_pages, total_pulled)."""
    local_seen = set()
    max_page = 0
    duplicate_pages = 0
    total_pulled = 0

    if not os.path.exists(location_dir):
        return local_seen, max_page, duplicate_pages, total_pulled

    # Restore from saved page files
    for path in Path(location_dir).glob("page_*.json"):
        local_seen.update(load_property_ids_from_file(path))
        try:
            page_num = int(path.stem.split("_")[-1])
            max_page = max(max_page, page_num)
        except ValueError:
            pass

    # Restore resume state if present
    state_path = os.path.join(location_dir, LOCATION_STATE_FILE)
    if os.path.exists(state_path):
        try:
            with open(state_path, "r", encoding="utf-8") as f:
                state = json.load(f)
            duplicate_pages = state.get("duplicate_pages", 0)
            total_pulled = state.get("total_pulled", 0)
            # Prefer the saved last_page if it is higher than max saved file
            saved_last_page = state.get("last_page", 0)
            if saved_last_page > max_page:
                max_page = saved_last_page
        except Exception:
            pass

    return local_seen, max_page, duplicate_pages, total_pulled


def scrape_locations(thread_id, locations_slice):
    """Worker: scrape a slice of locations in one thread, with resume support."""
    output_dir = os.path.join(OUTPUT_ROOT, f"thread_{thread_id}")
    log_file = f"{LOG_FILE_PREFIX}_thread_{thread_id}.log"
    os.makedirs(output_dir, exist_ok=True)

    # Per-thread state
    rotator = ProxyRotator(PROXY_FILE, min_requests=10, max_requests=20)
    thread_seen = load_thread_seen(output_dir)

    if shutdown_event.is_set():
        print(f"[THREAD {thread_id}] 🛑 shutdown requested before starting, exiting")
        return

    total_for_thread = 0
    skipped_completed = 0

    for idx, loc in enumerate(locations_slice, 1):
        combined = loc["combinedLocationIds"]
        lat = loc["latitude"]
        lng = loc["longitude"]

        location_dir = os.path.join(
            output_dir,
            combined.replace(",", "_")
        )
        os.makedirs(location_dir, exist_ok=True)

        # Skip if already fully completed in a previous run
        if is_location_completed(location_dir):
            skipped_completed += 1
            print(
                f"[THREAD {thread_id} LOCATION {idx}/{len(locations_slice)}] "
                f"{loc['text']} — already completed, skipping"
            )
            continue

        # Resume from saved state if any
        local_seen, max_page, duplicate_pages, total_pulled = load_location_state(location_dir)
        page = max_page + 1
        completed_normally = False

        print(
            f"[THREAD {thread_id} LOCATION {idx}/{len(locations_slice)}] "
            f"{loc['text']} — starting from page {page} "
            f"(restored {len(local_seen)} seen)"
        )

        while True:
            payload = {
                "combinedLocations": [combined],
                "contracts": [],
                "includePurchaseTypeFacets": True,
                "isMap": False,
                "latitude": lat,
                "longitude": lng,
                "pageNumber": page,
                "pageSize": PAGE_SIZE,
                "propertyType": 2,
                "sortOrderDesc": True,
                "sortType": "scoring",
                "transactionType": 1,
                "size": PAGE_SIZE,
                "isSuperTopVariant": False,
            }

            proxy = rotator.assign_proxy()

            try:
                r = requests.post(
                    BASE_URL,
                    json=payload,
                    headers=HEADERS,
                    proxy=proxy,
                    timeout=60,
                )

                if r.status_code != 200:
                    raise Exception(f"HTTP {r.status_code}")

                data = r.json()
                items = data.get("items", [])

                if not items:
                    print(f"  [T{thread_id}] → empty page {page}, stopping location")
                    completed_normally = True
                    break

                new_items = []
                duplicate_found = False

                for it in items:
                    pid = it.get("propertyId")
                    if not pid:
                        continue

                    # Intra-thread dedup only (cross-thread dupes handled later)
                    if pid in local_seen or pid in thread_seen:
                        duplicate_found = True
                    else:
                        local_seen.add(pid)
                        thread_seen.add(pid)
                        new_items.append(it)

                if duplicate_found:
                    duplicate_pages += 1
                    print(
                        f"  [T{thread_id}] ⚠ duplicate detected on page {page} "
                        f"({duplicate_pages})"
                    )
                    if duplicate_pages >= MAX_DUPLICATE_HITS:
                        print(
                            f"  [T{thread_id}] ⛔ stopping location (rotation detected)"
                        )
                        completed_normally = True
                        break
                else:
                    duplicate_pages = 0

                if new_items:
                    out_file = os.path.join(location_dir, f"page_{page}.json")
                    with open(out_file, "w", encoding="utf-8") as f:
                        json.dump({"items": new_items}, f, ensure_ascii=False)

                    total_pulled += len(new_items)
                    print(
                        f"  [T{thread_id}] ✓ page {page} new={len(new_items)} "
                        f"total={total_pulled}"
                    )

                # Persist resume state after every page
                save_location_state(location_dir, combined, page, duplicate_pages, total_pulled)

            except Exception as e:
                print(f"  [T{thread_id}] ❌ ERROR page {page}: {e}")
                log_error(log_file, combined, page, e)
                completed_normally = False
                break

            page += 1
            time.sleep(SLEEP)

            # Check for graceful shutdown request between pages
            if shutdown_event.is_set():
                print(f"  [T{thread_id}] 🛑 shutdown requested, stopping location cleanly")
                save_location_state(location_dir, combined, page - 1, duplicate_pages, total_pulled)
                break

        if completed_normally:
            mark_location_completed(location_dir, combined, total_pulled)

        total_for_thread += total_pulled
        print(
            f"[T{thread_id} DONE] {loc['text']} → {total_pulled} unique properties "
            f"(thread total: {total_for_thread}, skipped completed: {skipped_completed})"
        )

    print(f"\n✅ THREAD {thread_id} FINISHED — {total_for_thread} properties pulled "
          f"(skipped already completed: {skipped_completed})")


def split_locations(locations, n):
    """Split locations into n workload-balanced chunks using adsCount.

    Deterministic: same input always produces the same assignment,
    so each thread resumes the same locations on restart.
    """
    sorted_locs = sorted(
        locations,
        key=lambda loc: loc.get("adsCount", 0) or 0,
        reverse=True
    )

    chunks = [[] for _ in range(n)]
    chunk_workloads = [0] * n

    for loc in sorted_locs:
        min_idx = min(range(n), key=lambda i: chunk_workloads[i])
        chunks[min_idx].append(loc)
        chunk_workloads[min_idx] += loc.get("adsCount", 0) or 0

    return chunks, chunk_workloads


def main():
    with open(LOCATIONS_FILE, encoding="utf-8") as f:
        locations = json.load(f)

    # Filter out skipped locations
    skipped = [loc for loc in locations if loc["combinedLocationIds"] in SKIP_LOCATIONS]
    locations = [loc for loc in locations if loc["combinedLocationIds"] not in SKIP_LOCATIONS]

    # Filter out zero-ads locations if enabled
    if SKIP_ZERO_ADS:
        zero_ads = [loc for loc in locations if (loc.get("adsCount") or 0) == 0]
        locations = [loc for loc in locations if (loc.get("adsCount") or 0) > 0]
        print(f"[INFO] Loaded {len(locations) + len(skipped) + len(zero_ads)} locations, using {NUM_THREADS} threads")
        if skipped:
            for loc in skipped:
                print(f"[SKIP] {loc['text']} ({loc['combinedLocationIds']}) — adsCount: {loc.get('adsCount', 0):,}")
        print(f"[SKIP] {len(zero_ads)} location(s) with adsCount=0")
        print(f"[INFO] Remaining: {len(locations)} locations")
    else:
        print(f"[INFO] Loaded {len(locations) + len(skipped)} locations, using {NUM_THREADS} threads")
        if skipped:
            for loc in skipped:
                print(f"[SKIP] {loc['text']} ({loc['combinedLocationIds']}) — adsCount: {loc.get('adsCount', 0):,}")
            print(f"[INFO] Skipped {len(skipped)} location(s), {len(locations)} remaining")

    chunks, workloads = split_locations(locations, NUM_THREADS)
    actual_threads = min(NUM_THREADS, len(chunks))

    print(f"[INFO] Workload distribution (adsCount per thread):")
    for i, w in enumerate(workloads[:actual_threads], 1):
        loc_count = len(chunks[i - 1])
        print(f"  Thread {i}: {w:>10,} ads  ({loc_count:>4} locations)")

    threads = []
    for thread_id in range(actual_threads):
        t = threading.Thread(
            target=scrape_locations,
            args=(thread_id, chunks[thread_id]),
            name=f"ScraperThread-{thread_id}"
        )
        threads.append(t)
        t.start()

    try:
        # Poll with timeout so CTRL+C can be caught even on Windows
        while any(t.is_alive() for t in threads):
            for t in threads:
                t.join(timeout=0.5)
        print("\n✅ ALL THREADS FINISHED")
    except KeyboardInterrupt:
        print("\n[SHUTDOWN] CTRL+C detected. Stopping threads gracefully...")
        print("[SHUTDOWN] Waiting for current requests to finish (up to 60s each)...")
        shutdown_event.set()
        for t in threads:
            t.join(timeout=120)
        print("✅ Shutdown complete — state saved up to the last finished page")
        sys.exit(0)


if __name__ == "__main__":
    main()
