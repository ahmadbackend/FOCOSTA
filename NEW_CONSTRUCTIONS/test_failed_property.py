#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script to scrape the failed property and verify encoding fixes
"""

from curl_cffi import requests
from bs4 import BeautifulSoup
import json
import re
import sys

# Configure stdout to use UTF-8
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

def extract_property_data_from_html(html_content, property_url):
    """Extract property data from HTML by parsing __INITIAL_PROPS__"""
    try:
        soup = BeautifulSoup(html_content, 'html.parser')

        script_tags = soup.find_all('script')
        for script in script_tags:
            if script.string and '__INITIAL_PROPS__' in script.string:
                match = re.search(r'window\.__INITIAL_PROPS__\s*=\s*JSON\.parse\("(.+?)"\);', script.string, re.DOTALL)
                if match:
                    json_str = match.group(1)
                    json_str = json_str.encode().decode('unicode_escape')

                    data = json.loads(json_str)

                    if 'projectDetail' in data:
                        project = data['projectDetail']
                        advertiser = project.get('advertiser', {})

                        phone = advertiser.get('phone', 'N/A')
                        print(f"✓ Phone found: {phone}")
                        print(f"✓ Advertiser: {advertiser.get('promoterName', 'N/A')}")

                        return {
                            'phone_number': phone,
                            'advertiser_name': advertiser.get('promoterName'),
                        }

        return None
    except Exception as e:
        print(f"✗ Error: {e}")
        return None

# Test with the failed property
property_id = "20562767"
property_url = "https://www.fotocasa.es/es/comprar/obra-nueva/moncofa/20562767"

print(f"Testing property {property_id}...")
print(f"URL: {property_url}")

try:
    response = requests.get(
        property_url,
        timeout=30,
        impersonate="chrome120",
        headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        }
    )

    if response.status_code == 200:
        print(f"✓ HTTP {response.status_code}")

        # Save HTML for debugging
        with open('G:/FOTOCASA/NEW_CONSTRUCTIONS/test_property.html', 'w', encoding='utf-8', errors='surrogateescape') as f:
            f.write(response.text)
        print("✓ HTML saved to test_property.html")

        data = extract_property_data_from_html(response.text, property_url)

        if data:
            # Test writing to file
            with open('G:/FOTOCASA/NEW_CONSTRUCTIONS/test_property.json', 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print("✓ JSON saved successfully")

            # Test writing to log file
            with open('G:/FOTOCASA/NEW_CONSTRUCTIONS/test_failed.log', 'w', encoding='utf-8', errors='surrogateescape') as f:
                f.write(f"{property_id}|{property_url}|SUCCESS\n")
            print("✓ Log file written successfully")
        else:
            print("✗ No data extracted")
    else:
        print(f"✗ HTTP {response.status_code}")

except Exception as e:
    error_msg = str(e).encode('utf-8', errors='replace').decode('utf-8')
    print(f"✗ Exception: {error_msg}")

    # Test error handling
    with open('G:/FOTOCASA/NEW_CONSTRUCTIONS/test_failed.log', 'w', encoding='utf-8', errors='surrogateescape') as f:
        f.write(f"{property_id}|{property_url}|{error_msg}\n")
    print("✓ Error logged successfully")

print("\nTest completed!")
