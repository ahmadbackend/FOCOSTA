import os
import json
from curl_cffi import requests
from proxy_rotator import ProxyRotator

# ---------------- CONFIG ----------------
BASE_URL = "https://web.gw.fotocasa.es/v1/search/ads"
PROXY_FILE = os.environ.get("FC_PROXY_FILE", "decodo_scraper_ips.txt")
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

# A few test locations (province-level)
TEST_LOCATIONS = [
    "724,7,40,0,0,0,0,0,0",   # Madrid province
    "724,9,8,0,0,0,0,0,0",    # Barcelona province
    "724,0,2,0,0,0,0,0,0",    # Albacete province
]

PAGE_SIZE = int(os.environ.get("FC_PAGE_SIZE", 30))
MAX_PAGES_PER_LOCATION = 5


def is_particular(item):
    agency = item.get("agency") or {}
    return agency.get("type") == "particular"


def fetch_page(rotator, combined, page):
    payload = {
        "combinedLocations": [combined],
        "contracts": [],
        "includePurchaseTypeFacets": True,
        "isMap": False,
        "pageNumber": page,
        "pageSize": PAGE_SIZE,
        "propertyType": 2,
        "sortOrderDesc": True,
        "sortType": "publicationDate",
        "transactionType": 1,
        "size": PAGE_SIZE,
        "isSuperTopVariant": False,
    }

    proxy = rotator.assign_proxy()
    r = requests.post(BASE_URL, json=payload, headers=HEADERS, proxy=proxy, timeout=60)
    r.raise_for_status()
    return r.json()


def main():
    rotator = ProxyRotator(PROXY_FILE, min_requests=10, max_requests=20)

    for combined in TEST_LOCATIONS:
        print(f"\n{'='*60}")
        print(f"Testing location: {combined}")
        print(f"{'='*60}")

        total_scanned = 0
        total_particular = 0
        particulars = []

        for page in range(1, MAX_PAGES_PER_LOCATION + 1):
            try:
                data = fetch_page(rotator, combined, page)
            except Exception as e:
                print(f"  [ERROR] page {page}: {e}")
                break

            items = data.get("items", [])
            if not items:
                print(f"  Page {page}: empty, stopping")
                break

            page_particulars = [it for it in items if is_particular(it)]

            total_scanned += len(items)
            total_particular += len(page_particulars)
            particulars.extend(page_particulars)

            print(
                f"  Page {page}: scanned={len(items)}, "
                f"particular={len(page_particulars)}"
            )

        print(f"\n  SUMMARY: scanned={total_scanned}, particular={total_particular}")
        if particulars:
            print(f"  Sample particular listings:")
            for it in particulars[:3]:
                agency = it.get("agency") or {}
                print(
                    f"    - propertyId={it.get('propertyId')}, "
                    f"agency='{agency.get('name')}', "
                    f"type='{agency.get('type')}', "
                    f"price={it.get('price', {}).get('amount') if isinstance(it.get('price'), dict) else it.get('price')}"
                )

        # Save particulars for manual inspection
        out_file = f"test_particulars_{combined.replace(',', '_')}.json"
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(particulars, f, ensure_ascii=False, indent=2)
        print(f"  Saved particulars to: {out_file}")


if __name__ == "__main__":
    main()
