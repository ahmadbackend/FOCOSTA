import os
import json
import time
from curl_cffi import requests

from proxy_rotator import ProxyRotator

# Load agencies
with open("unique_agencies_urgent.json", "r", encoding="utf-8") as f:
    agencies = json.load(f)

PROXY_FILE = os.environ.get("FC_PROXY_FILE", "decodo_scraper_ips.txt")
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",
    "Content-Type": "application/json",

}

rotator = ProxyRotator(PROXY_FILE, min_requests=10, max_requests=20)

# Only enrich private sellers (particular)
particular_agencies = [a for a in agencies if a.get("type") == "particular"]
print(f"[INFO] {len(particular_agencies)} particular agencies out of {len(agencies)} total")

for agency in particular_agencies:
    publisher_id = agency["publisher_id"]
    # POST URL must use the tracking endpoint with publisher_id
    url = f"https://web.gw.fotocasa.es/v1/publishers/{publisher_id}/tracking-phone"

    payload = {
        "listingUrl": agency["agency_abs_path"],  # dynamic listing URL
        "marketplace": "FOTOCASA",
        "platform": "web",
        "userAgent": HEADERS["User-Agent"]
    }

    proxy = rotator.assign_proxy()
    try:
        response = requests.post(url, json=payload, headers=HEADERS, proxy=proxy)
        data = response.json()
        tracking_phone = data.get("trackingPhone")
        print(f"{agency['agency name']} -> {tracking_phone}")
        # Append the phone directly to the agency dict
        agency["tracking_phone"] = tracking_phone
    except Exception as e:
        print(f"Error for {agency['agency name']}: {e}")
        agency["tracking_phone"] = None

    time.sleep(1)  # 1-second delay

# Save the updated agencies JSON (particular only)
with open("agencies_with_phone_urgent.json", "w") as f:
    json.dump(particular_agencies, f, indent=2)
