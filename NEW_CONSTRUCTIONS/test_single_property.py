from curl_cffi import requests
from bs4 import BeautifulSoup
import json
import re

# Test single property
test_url = "https://www.fotocasa.es/es/comprar/obra-nueva/begues/20528373"

PROXY_URL = "http://customer-AHMAD_NSPT0-cc-US:fCpqqylS70igFo+j@us-pr.oxylabs.io:10000"

print(f"Testing: {test_url}")

try:
    session = requests.Session(impersonate="chrome120")
    # Using NEW US Proxy
    session.proxies = {
        "http": PROXY_URL,
        "https": PROXY_URL
    }

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'es-ES,es;q=0.9,en-US;q=0.8,en;q=0.7',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Cache-Control': 'max-age=0',
        'Upgrade-Insecure-Requests': '1',
        'Referer': 'https://www.fotocasa.es/es/promociones-obra-nueva/comprar/viviendas/espana/todas-las-zonas/l',
    }

    print("Sending request...")
    response = session.get(test_url, headers=headers, timeout=45, allow_redirects=True)

    print(f"Status Code: {response.status_code}")
    print(f"Response Length: {len(response.text)} bytes")

    if response.status_code == 200:
        # Try to find phone number
        soup = BeautifulSoup(response.text, 'html.parser')
        script_tags = soup.find_all('script')

        for script in script_tags:
            if script.string and '__INITIAL_PROPS__' in script.string:
                match = re.search(r'window\.__INITIAL_PROPS__\s*=\s*JSON\.parse\("(.+?)"\);', script.string, re.DOTALL)
                if match:
                    json_str = match.group(1)
                    json_str = json_str.encode().decode('unicode_escape')
                    data = json.loads(json_str)

                    # Extract phone
                    phone = data.get('projectDetail', {}).get('advertiser', {}).get('phone')
                    title = data.get('projectDetail', {}).get('name')

                    print(f"\n✅ SUCCESS!")
                    print(f"Title: {title}")
                    print(f"Phone: {phone}")
                    break
        else:
            print("\n⚠️ No __INITIAL_PROPS__ found")
    else:
        print(f"\n❌ FAILED with status {response.status_code}")
        print(f"Response preview: {response.text[:500]}")

except Exception as e:
    print(f"\n❌ ERROR: {e}")
