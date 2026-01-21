from curl_cffi import requests
from bs4 import BeautifulSoup
import json
import re
import logging
import time
import os

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('retry_scraper.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

# Configuration
BASE_URL = "https://www.fotocasa.es/es/promociones-obra-nueva/comprar/viviendas/espana/todas-las-zonas/l/{}"
PROXY_URL = "http://customer-AHMAD_NSPT0-cc-US:fCpqqylS70igFo+j@pr.oxylabs.io:7777"
OUTPUT_DIR = "output"
RETRY_LOG = "retry_results.log"

def get_session_with_proxy():
    """Create a session with proxy"""
    session = requests.Session(impersonate="chrome110")
    session.proxies = {
        "http": PROXY_URL,
        "https": PROXY_URL
    }
    return session

def extract_property_links(html_content):
    """Extract property links from the HTML content"""
    try:
        soup = BeautifulSoup(html_content, 'html.parser')

        # Find the script tag with __INITIAL_PROPS__
        script_tags = soup.find_all('script')
        for script in script_tags:
            if script.string and '__INITIAL_PROPS__' in script.string:
                # Extract JSON data
                match = re.search(r'window\.__INITIAL_PROPS__\s*=\s*JSON\.parse\("(.+?)"\);', script.string, re.DOTALL)
                if match:
                    json_str = match.group(1)
                    # Unescape the JSON string
                    json_str = json_str.encode().decode('unicode_escape')

                    try:
                        data = json.loads(json_str)

                        # Extract property links from realEstates
                        property_links = []

                        if 'initialSearch' in data and 'result' in data['initialSearch']:
                            result = data['initialSearch']['result']

                            # Get realEstates (individual properties)
                            if 'realEstates' in result:
                                for estate in result['realEstates']:
                                    if 'detail' in estate and 'es-ES' in estate['detail']:
                                        detail_url = estate['detail']['es-ES']
                                        full_url = f"https://www.fotocasa.es{detail_url}"
                                        property_links.append({
                                            'url': full_url,
                                            'id': estate.get('id'),
                                            'price': estate.get('rawPrice'),
                                            'location': estate.get('location'),
                                            'type': 'realEstate'
                                        })

                            # Get promotionClassifieds (new construction promotions)
                            if 'promotionClassifieds' in result:
                                for promo in result['promotionClassifieds']:
                                    if 'detail' in promo and 'es-ES' in promo['detail']:
                                        detail_url = promo['detail']['es-ES']
                                        full_url = f"https://www.fotocasa.es{detail_url}"
                                        property_links.append({
                                            'url': full_url,
                                            'id': promo.get('id'),
                                            'price': promo.get('rawPrice'),
                                            'location': promo.get('location'),
                                            'promotionTitle': promo.get('promotionTitle'),
                                            'type': 'promotion'
                                        })

                        return property_links
                    except json.JSONDecodeError as e:
                        logging.error(f"JSON decode error: {e}")
                        return []

        logging.warning("No __INITIAL_PROPS__ found in page")
        return []

    except Exception as e:
        logging.error(f"Error extracting property links: {e}")
        return []

def scrape_page(page_num):
    """Scrape a single page"""
    # First page doesn't have page number, others use /2, /3, etc
    if page_num == 1:
        url = "https://www.fotocasa.es/es/promociones-obra-nueva/comprar/viviendas/espana/todas-las-zonas/l"
    else:
        url = BASE_URL.format(page_num)

    try:
        # Create a new session for each request
        session = get_session_with_proxy()

        logging.info(f"Retrying page {page_num}: {url}")

        # Add headers to mimic browser
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }

        response = session.get(url, headers=headers, timeout=30)
        response.raise_for_status()

        # Extract property links
        property_links = extract_property_links(response.text)

        if property_links:
            # Save to individual file
            output_file = f"{OUTPUT_DIR}/page_{page_num:03d}.json"
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'page': page_num,
                    'url': url,
                    'count': len(property_links),
                    'properties': property_links
                }, f, ensure_ascii=False, indent=2)

            logging.info(f"[SUCCESS] Page {page_num}: {len(property_links)} properties found")
            with open(RETRY_LOG, 'a', encoding='utf-8') as f:
                f.write(f"[SUCCESS] Page {page_num}: {len(property_links)} properties\n")
            return {'success': True, 'page': page_num, 'count': len(property_links)}
        else:
            logging.warning(f"[NO DATA] Page {page_num}: No properties found")
            with open(RETRY_LOG, 'a', encoding='utf-8') as f:
                f.write(f"[NO DATA] Page {page_num}: No properties found\n")
            return {'success': False, 'page': page_num, 'error': 'No properties found'}

    except Exception as e:
        error_msg = str(e)
        logging.error(f"[ERROR] Page {page_num}: {error_msg}")
        with open(RETRY_LOG, 'a', encoding='utf-8') as f:
            f.write(f"[ERROR] Page {page_num}: {error_msg}\n")
        return {'success': False, 'page': page_num, 'error': error_msg}

def parse_failed_pages():
    """Parse failed_pages.log to get list of failed page numbers"""
    failed_pages = []
    try:
        with open('failed_pages.log', 'r', encoding='utf-8') as f:
            for line in f:
                # Extract page number from "Page X:"
                match = re.search(r'Page (\d+):', line)
                if match:
                    page_num = int(match.group(1))
                    if page_num not in failed_pages:
                        failed_pages.append(page_num)
    except FileNotFoundError:
        logging.error("failed_pages.log not found!")
        return []

    return sorted(failed_pages)

def merge_with_existing():
    """Merge retry results with all_properties.json"""
    import glob

    # Load existing properties
    existing_properties = []
    existing_ids = set()

    try:
        with open('all_properties.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
            existing_properties = data.get('properties', [])
            existing_ids = {p.get('id') for p in existing_properties if p.get('id')}
            logging.info(f"Loaded {len(existing_properties)} existing properties")
    except FileNotFoundError:
        logging.warning("all_properties.json not found, will create new file")

    # Read all page files (including new retry results)
    page_files = sorted(glob.glob(f"{OUTPUT_DIR}/page_*.json"))

    new_properties = []
    duplicate_count = 0

    for page_file in page_files:
        try:
            with open(page_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for prop in data.get('properties', []):
                    prop_id = prop.get('id')
                    # Only add if not duplicate
                    if prop_id and prop_id not in existing_ids:
                        new_properties.append(prop)
                        existing_ids.add(prop_id)
                    elif prop_id:
                        duplicate_count += 1
        except Exception as e:
            logging.error(f"Error reading {page_file}: {e}")

    # Combine all properties
    all_properties = existing_properties + new_properties

    # Save merged results
    output_file = "all_properties.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            'total_properties': len(all_properties),
            'properties': all_properties
        }, f, ensure_ascii=False, indent=2)

    logging.info(f"Merged: {len(existing_properties)} existing + {len(new_properties)} new = {len(all_properties)} total")
    logging.info(f"Skipped {duplicate_count} duplicates")

    # Update links file
    links_file = "property_links.txt"
    with open(links_file, 'w', encoding='utf-8') as f:
        for prop in all_properties:
            f.write(f"{prop['url']}\n")

    logging.info(f"Updated {links_file} with all property URLs")

def main():
    # Clear retry log
    open(RETRY_LOG, 'w', encoding='utf-8').close()

    # Get failed pages
    failed_pages = parse_failed_pages()

    if not failed_pages:
        logging.info("No failed pages to retry!")
        return

    logging.info(f"Found {len(failed_pages)} failed pages to retry: {failed_pages}")

    successful = 0
    failed = 0

    # Retry each page one by one (single-threaded)
    for page_num in failed_pages:
        result = scrape_page(page_num)

        if result['success']:
            successful += 1
        else:
            failed += 1

        # Wait a bit between requests to avoid rate limiting
        time.sleep(2)

    logging.info(f"\n{'='*60}")
    logging.info(f"Retry completed: {successful} successful, {failed} failed")
    logging.info(f"{'='*60}\n")

    # Merge with existing data
    if successful > 0:
        logging.info("Merging retry results with all_properties.json...")
        merge_with_existing()
        logging.info("Merge complete!")
    else:
        logging.info("No successful retries to merge")

if __name__ == "__main__":
    main()
