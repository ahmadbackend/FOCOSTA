import json
import os
import time
from curl_cffi import requests

from proxy_rotator import ProxyRotator

# ---------------- CONFIG ----------------
BASE_URL = "https://web.gw.fotocasa.es/v1/search/ads"

FAILED_LOG = os.environ.get("FC_FAILED_LOG", "failed_requests.log")
LOCATIONS_FILE = os.environ.get("FC_LOCATIONS_FILE", "fotocasa_locations.json")
OUTPUT_DIR = os.environ.get("FC_OUTPUT_DIR", "fotocasa_clean_properties")
PROXY_FILE = os.environ.get("FC_PROXY_FILE", "decodo_scraper_ips.txt")
PAGE_SIZE = int(os.environ.get("FC_PAGE_SIZE", 30))
SLEEP = float(os.environ.get("FC_SLEEP", 0.4))  # ---------------- HEADERS ----------------
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Content-Type": "application/json",
    "Accept": "application/json",
    "Origin": "https://www.fotocasa.es",
    "Referer": "https://www.fotocasa.es/",
}

# ---------------- LOAD LOCATIONS ----------------
with open(LOCATIONS_FILE, encoding="utf-8") as f:
    locations = {l["combinedLocationIds"]: l for l in json.load(f)}

# ---------------- LOAD FAILED ----------------
failed = []
with open(FAILED_LOG, encoding="utf-8") as f:
    for line in f:
        try:
            failed.append(json.loads(line))
        except:
            pass

print(f"[INFO] Loaded {len(failed)} failed pages")

# ---------------- LOAD GLOBAL SEEN IDS ----------------
GLOBAL_SEEN = set()

for root, _, files in os.walk(OUTPUT_DIR):
    for fn in files:
        if not fn.endswith(".json"):
            continue
        with open(os.path.join(root, fn), encoding="utf-8") as f:
            try:
                data = json.load(f)
                for it in data.get("items", []):
                    pid = it.get("propertyId")
                    if pid:
                        GLOBAL_SEEN.add(pid)
            except:
                pass

print(f"[INFO] Loaded {len(GLOBAL_SEEN)} existing propertyIds")

# ---------------- RETRY ----------------
rotator = ProxyRotator(PROXY_FILE, min_requests=10, max_requests=20)

for rec in failed:
    combined = rec["location"]
    page = rec["page"]

    loc = locations.get(combined)
    if not loc:
        print(f"[SKIP] Location not found: {combined}")
        continue

    lat = loc["latitude"]
    lng = loc["longitude"]

    location_dir = os.path.join(OUTPUT_DIR, combined.replace(",", "_"))
    os.makedirs(location_dir, exist_ok=True)

    out_file = os.path.join(location_dir, f"page_{page}.json")

    if os.path.exists(out_file):
        print(f"[SKIP] Already exists {combined} page {page}")
        continue

    print(f"[RETRY] {combined} page {page}")

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

        new_items = []
        for it in items:
            pid = it.get("propertyId")
            if pid and pid not in GLOBAL_SEEN:
                GLOBAL_SEEN.add(pid)
                new_items.append(it)

        if new_items:
            with open(out_file, "w", encoding="utf-8") as f:
                json.dump({"items": new_items}, f, ensure_ascii=False)
            print(f"  ✓ recovered {len(new_items)} properties")
        else:
            print("  ⚠ no new properties (rotation or duplicate)")

    except Exception as e:
        print(f"  ❌ still failing: {e}")

    time.sleep(SLEEP)

print("\n✅ Failed-page recovery finished")
