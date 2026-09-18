import json
import math
import os
import string
import threading
import time
from curl_cffi import requests

from proxy_rotator import ProxyRotator

# ---------------- CONFIG ----------------
API_URL = "https://search.gw.fotocasa.es/v2/suggest"
OUTPUT_FILE = os.environ.get("FC_OUTPUT_FILE", "fotocasa_locations_depth3.json")
PROXY_FILE = os.environ.get("FC_PROXY_FILE", "decodo_scraper_ips.txt")
NUM_THREADS = int(os.environ.get("FC_NUM_THREADS", 26))
SLEEP = float(os.environ.get("FC_SLEEP", 0.2))
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Content-Type": "application/json",
    "Accept": "application/json",
    "Origin": "https://www.fotocasa.es",
    "Referer": "https://www.fotocasa.es/",
}

# ---------------------------------------

def generate_queries(depth=3):
    chars = string.ascii_lowercase
    if depth == 1:
        for c in chars:
            yield c
    elif depth == 2:
        for a in chars:
            for b in chars:
                yield a + b
    elif depth == 3:
        for a in chars:
            for b in chars:
                for c in chars:
                    yield a + b + c


def fetch_locations(query, proxy=None):
    payload = {
        "query": query,
        "filters": {
            "propertyTypeFilter": "HOME",
            "transactionTypeFilter": "SALE"
        }
    }

    request_kwargs = {
        "json": payload,
        "headers": HEADERS,
        "timeout": 30,
    }
    if proxy:
        request_kwargs["proxy"] = proxy

    r = requests.post(API_URL, **request_kwargs)

    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code}")

    return r.json()


def worker(thread_id, queries, locations, lock, total_seen_counter):
    rotator = ProxyRotator(PROXY_FILE, min_requests=10, max_requests=20)
    local_added = 0
    local_seen = 0

    for idx, q in enumerate(queries, 1):
        proxy = rotator.assign_proxy()
        try:
            results = fetch_locations(q, proxy=proxy)
        except Exception as e:
            print(f"[WARN] [T{thread_id}] {q} failed: {e}")
            continue

        added = 0
        for item in results:
            cid = item.get("combinedLocationIds")
            if not cid:
                continue

            with lock:
                if cid not in locations:
                    locations[cid] = {
                        "combinedLocationIds": cid,
                        "latitude": item.get("coordinates", {}).get("latitude"),
                        "longitude": item.get("coordinates", {}).get("longitude"),
                        "text": item.get("text"),
                        "baseText": item.get("baseText"),
                        "type": item.get("type"),
                        "groupCategory": item.get("groupCategory"),
                        "adsCount": item.get("adsCount"),
                    }
                    added += 1

        local_added += added
        local_seen += len(results)

        if idx % 10 == 0 or idx == len(queries):
            print(
                f"[T{thread_id}] {idx}/{len(queries)} "
                f"seen={local_seen} added={local_added} "
                f"global_unique={len(locations)}"
            )

        time.sleep(SLEEP)

    with lock:
        total_seen_counter[0] += local_seen


def split_queries(queries, n):
    queries = list(queries)
    chunk_size = math.ceil(len(queries) / n)
    return [
        queries[i:i + chunk_size]
        for i in range(0, len(queries), chunk_size)
    ]


def main():
    all_queries = list(generate_queries(depth=3))
    print(f"[INFO] Total queries to run: {len(all_queries)}")
    print(f"[INFO] Using {NUM_THREADS} threads (~{len(all_queries) // NUM_THREADS} queries each)")

    chunks = split_queries(all_queries, NUM_THREADS)
    actual_threads = min(NUM_THREADS, len(chunks))

    locations = {}
    lock = threading.Lock()
    total_seen_counter = [0]

    threads = []
    for thread_id in range(actual_threads):
        t = threading.Thread(
            target=worker,
            args=(thread_id, chunks[thread_id], locations, lock, total_seen_counter),
            name=f"HarvesterThread-{thread_id}"
        )
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(list(locations.values()), f, ensure_ascii=False, indent=2)

    print(f"\n✅ DONE — saved {len(locations)} unique locations to {OUTPUT_FILE}")
    print(f"   Total API results seen: {total_seen_counter[0]}")


if __name__ == "__main__":
    main()
