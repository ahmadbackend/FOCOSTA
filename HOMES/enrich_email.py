import os
import json
import time
import re
from curl_cffi import requests

from proxy_rotator import ProxyRotator

# Load previously enriched agencies JSON
with open("agencies_with_phone_urgent.json", "r", encoding="utf-8") as f:
    agencies = json.load(f)

PROXY_FILE = os.environ.get("FC_PROXY_FILE", "decodo_scraper_ips.txt")
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36"
}

# Regex pattern to extract mailto link
EMAIL_REGEX = re.compile(r'href="mailto:([^"]+)"')
WEBSITE_REGEX = re.compile(r'<div class="re-MinisiteAgencyInfo-logo[^"]*">.*?<a[^>]+href="([^"]+)"', re.DOTALL)

rotator = ProxyRotator(PROXY_FILE, min_requests=10, max_requests=20)

# Only enrich private sellers (particular)
particular_agencies = [a for a in agencies if a.get("type") == "particular"]
print(f"[INFO] {len(particular_agencies)} particular agencies out of {len(agencies)} total")

for agency in particular_agencies:
    url = agency["agency_abs_path"]
    proxy = rotator.assign_proxy()
    try:
        response = requests.get(url, headers=HEADERS, proxy=proxy)
        html = response.text
        match = EMAIL_REGEX.search(html)
        email = match.group(1) if match else None
        agency["email"] = email
        match_site = WEBSITE_REGEX.search(html)
        website = match_site.group(1) if match_site else None
        agency["website"] = website
        print(f"{agency['agency name']} -> {website} {email}")
    except Exception as e:
        print(f"Error fetching {agency['agency name']}: {e}")
        agency["email"] = None

    time.sleep(1)  # 1-second delay

# Save updated agencies JSON (particular only)
with open("agencies_with_phone_email_urgent.json", "w", encoding="utf-8") as f:
    json.dump(particular_agencies, f, indent=2, ensure_ascii=False)
