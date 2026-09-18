import json
import time
import os
from curl_cffi import requests

from proxy_rotator import ProxyRotator

# -------- CONFIG --------
BASE_URL = "https://web.gw.fotocasa.es/v1/search/ads"

FAILED_LOG = os.environ.get("FC_FAILED_LOG", "missed_failed.log")
RETRY_FAILED_LOG = os.environ.get("FC_RETRY_FAILED_LOG", "retry_failed.log")
OUTPUT_DIR = os.environ.get("FC_OUTPUT_DIR", "missed_properties_mt")
SLEEP_BETWEEN_REQUESTS = float(os.environ.get("FC_SLEEP_BETWEEN_REQUESTS", 1.2))
MAX_RETRIES = int(os.environ.get("FC_MAX_RETRIES", 2))
PROXY_FILE = os.environ.get("FC_PROXY_FILE", "decodo_scraper_ips.txt")
PAGE_SIZE_REQUESTED = int(os.environ.get("FC_PAGE_SIZE_REQUESTED", 30))  # -------- HEADERS --------
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

os.makedirs(OUTPUT_DIR, exist_ok=True)

# -------- LOAD FAILED PAGES --------
failed_pages = set()

with open(FAILED_LOG, "r", encoding="utf-8") as f:
    for line in f:
        try:
            data = json.loads(line.strip())
            page = int(data.get("page"))
            failed_pages.add(page)
        except Exception:
            continue

failed_pages = sorted(failed_pages)

print(f"[INFO] Loaded {len(failed_pages)} unique failed pages")

# -------- HELPERS --------
def log_retry_failed(page, error):
    with open(RETRY_FAILED_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps({
            "page": page,
            "error": str(error)
        }) + "\n")


# -------- RETRY LOOP --------
rotator = ProxyRotator(PROXY_FILE, min_requests=10, max_requests=20)

for idx, page_number in enumerate(failed_pages, 1):
    print(f"[RETRY] {idx}/{len(failed_pages)} page={page_number}")

    payload = {
        "combinedLocations": ["724,0,0,0,0,0,0,0,0"],
        "contracts": [],
        "includePurchaseTypeFacets": True,
        "isMap": False,
        "pageNumber": page_number,
        "pageSize": PAGE_SIZE_REQUESTED,
        "propertyType": 2,
        "sortOrderDesc": True,
        "sortType": "publicationDate",
        "transactionType": 1,
        "size": PAGE_SIZE_REQUESTED,
    }

    success = False

    for attempt in range(1, MAX_RETRIES + 1):
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
                raise Exception("Empty items on retry")

            filename = os.path.join(
                OUTPUT_DIR,
                f"retried_page_{page_number}.json"
            )

            with open(filename, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            print(f"[OK] Page {page_number} recovered ({len(items)} items)")
            success = True
            break

        except Exception as e:
            print(f"[FAIL] Page {page_number} attempt {attempt}: {e}")
            time.sleep(2)

    if not success:
        log_retry_failed(page_number, "All retries failed")

    time.sleep(SLEEP_BETWEEN_REQUESTS)

print("[DONE] Retry pass completed")
