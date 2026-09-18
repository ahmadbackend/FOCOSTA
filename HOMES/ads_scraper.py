import json
import time
import os
from numbers import Number

from curl_cffi import requests
from itertools import cycle

from ijson.backends.yajl2_cffi import null
from proxy_rotator import ProxyRotator

# --- CONFIG ---
#pages = [2955, 2968, 2991, 3191, 3303, 3359, 3382, 3418, 3573, 3640, 3674, 3965, 4204, 4356, 4387, 4581, 4642, 4718, 4733, 4812, 4861, 5008, 5015, 5075, 5283, 5337, 5542, 5629, 5671, 5705, 5812, 5956, 6084, 6108, 6326, 6403, 6558, 6679, 6723, 6924, 6928, 7317, 7324, 7401, 7475, 7507, 7546]#, 65, 251, 324, 401, 429, 538, 625, 895, 1131, 1158, 1387, 1513, 1515, 1640, 1677, 1795, 1842, 1948, 2189, 2378, 2523, 2785, 2791]
#pages=[60000]
BASE_URL = "https://web.gw.fotocasa.es/v1/search/ads"
TOTAL_PROPERTIES = 448627
PAGE_SIZE = int(os.environ.get("FC_PAGE_SIZE", 8))
SLEEP_BETWEEN_REQUESTS = int(os.environ.get("FC_SLEEP_BETWEEN_REQUESTS", 0))  # seconds
OUTPUT_DIR = os.environ.get("FC_OUTPUT_DIR", "output")
LOG_FILE = os.environ.get("FC_LOG_FILE", "out_failed.log")
RESUME_FILE = "last_output_page.txt"
PROXY_FILE = os.environ.get("FC_PROXY_FILE", "decodo_scraper_ips.txt")  #proxy_pool = cycle(PROXIES)  # rotate proxies automatically

# --- HEADERS ---
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/115.0.5790.170 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json",
    "Referer": "https://www.fotocasa.es/",
    "Origin": "https://www.fotocasa.es"
}

# --- Helpers ---
def save_resume(page_number):
    with open(RESUME_FILE, "w") as f:
        f.write(str(page_number))

def load_resume():
    if os.path.exists(RESUME_FILE):
        with open(RESUME_FILE, "r") as f:
            return int(f.read().strip())
    return 1

def save_failed(page_number, payload, error):
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps({"page": page_number, "payload": payload, "error": str(error)}, ensure_ascii=False) + "\n")

# --- Prepare folders ---
os.makedirs(OUTPUT_DIR, exist_ok=True)

# --- Start scraping ---
start_page = load_resume()
total_pages = (TOTAL_PROPERTIES + PAGE_SIZE - 1) // PAGE_SIZE
rotator = ProxyRotator(PROXY_FILE, min_requests=10, max_requests=20)

for page_number in range(start_page, total_pages + 1):
    payload = {
        "combinedLocations": ["724,0,0,0,0,0,0,0,0"],
        "contracts": [],
        "includePurchaseTypeFacets": True,
        "isMap": False,
        "pageNumber": page_number,
        "pageSize": PAGE_SIZE,
        "propertyType": 2,
        "sortOrderDesc": True,
        "sortType": "publicationDate",
        "transactionType": 1,
        "size": PAGE_SIZE,
        "userId":""
    }

    # Rotate proxy
    proxy = rotator.assign_proxy()
    # Organize subfolder per 100 pages
    subfolder = os.path.join(OUTPUT_DIR, f"pages__missed_{((page_number-1)//100)*100+1}_{((page_number-1)//100+1)*100}")
    os.makedirs(subfolder, exist_ok=True)

    try:
        response = requests.post(
            BASE_URL,
            json=payload,
            headers=HEADERS,
            proxy=proxy,
            timeout=60  # seconds
        )

        if response.status_code == 200:
            filename = os.path.join(subfolder, f"fotocasa_page_{page_number}.json")
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(response.json(), f, ensure_ascii=False, indent=2)
            print(f"[+] Saved page {page_number} -> {filename}")
            save_resume(page_number + 1)
        else:
            print(f"[!] Failed page {page_number}, status code: {response.status_code}")
            save_failed(page_number, payload, f"Status code {response.status_code}")

    except Exception as e:
        print(f"[!] Exception on page {page_number}: {e}")
        save_failed(page_number, payload, e)

    time.sleep(SLEEP_BETWEEN_REQUESTS)

print("[*] Scraping finished!")
