from curl_cffi import requests
from bs4 import BeautifulSoup
import json
import re
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import random
import threading
import os

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(threadName)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('scraper.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

# Configuration
BASE_URL = "https://www.fotocasa.es/es/promociones-obra-nueva/comprar/viviendas/espana/todas-las-zonas/l/{}"
TOTAL_PAGES = 43
MAX_THREADS = 30
PROXY_URL = "http://customer-AHMAD_NSPT0-cc-US:fCpqqylS70igFo+j@pr.oxylabs.io:7777"
OUTPUT_DIR = "output"
FAILED_LOG = "failed_pages.log"

# Thread-safe counters
lock = threading.Lock()
successful_pages = 0
failed_pages = 0

def get_session_with_random_proxy():
    """Create a session with proxy that rotates by session"""
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
    global successful_pages, failed_pages

    # First page doesn't have page number, others use /2, /3, etc
    if page_num == 1:
        url = "https://www.fotocasa.es/es/promociones-obra-nueva/comprar/viviendas/espana/todas-las-zonas/l"
    else:
        url = BASE_URL.format(page_num)

    try:
        # Create a new session for each request (new IP)
        session = get_session_with_random_proxy()

        logging.info(f"Scraping page {page_num}: {url}")

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

            with lock:
                successful_pages += 1

            logging.info(f"Page {page_num} completed: {len(property_links)} properties found")
            return {'success': True, 'page': page_num, 'count': len(property_links)}
        else:
            logging.warning(f"Page {page_num}: No properties found")
            with lock:
                failed_pages += 1
            with open(FAILED_LOG, 'a') as f:
                f.write(f"Page {page_num}: No properties found\n")
            return {'success': False, 'page': page_num, 'error': 'No properties found'}

    except Exception as e:
        with lock:
            failed_pages += 1
        logging.error(f"Page {page_num} failed: {str(e)}")
        with open(FAILED_LOG, 'a') as f:
            f.write(f"Page {page_num}: {str(e)}\n")
        return {'success': False, 'page': page_num, 'error': str(e)}

def merge_results():
    """Merge all individual JSON files into one"""
    import glob

    all_properties = []

    # Read all page files
    page_files = sorted(glob.glob(f"{OUTPUT_DIR}/page_*.json"))

    for page_file in page_files:
        try:
            with open(page_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                all_properties.extend(data['properties'])
        except Exception as e:
            logging.error(f"Error reading {page_file}: {e}")

    # Save merged results
    output_file = "all_properties.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            'total_properties': len(all_properties),
            'properties': all_properties
        }, f, ensure_ascii=False, indent=2)

    logging.info(f"Merged {len(all_properties)} properties into {output_file}")

    # Create a simple links file
    links_file = "property_links.txt"
    with open(links_file, 'w', encoding='utf-8') as f:
        for prop in all_properties:
            f.write(f"{prop['url']}\n")

    logging.info(f"Created {links_file} with all property URLs")

def main():
    # Create output directory
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Clear failed log
    open(FAILED_LOG, 'w').close()

    logging.info(f"Starting scraper for {TOTAL_PAGES} pages with {MAX_THREADS} threads")

    start_time = time.time()

    # Use ThreadPoolExecutor for concurrent scraping
    with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
        # Submit all pages
        futures = {executor.submit(scrape_page, page): page for page in range(1, TOTAL_PAGES + 1)}

        # Process completed tasks
        for future in as_completed(futures):
            page = futures[future]
            try:
                result = future.result()
                if result['success']:
                    logging.info(f"[SUCCESS] Page {result['page']}: {result['count']} properties")
                else:
                    logging.error(f"[FAILED] Page {result['page']}: {result['error']}")
            except Exception as e:
                logging.error(f"Exception for page {page}: {e}")

    elapsed_time = time.time() - start_time

    logging.info(f"\n{'='*60}")
    logging.info(f"Scraping completed in {elapsed_time:.2f} seconds")
    logging.info(f"Successful pages: {successful_pages}/{TOTAL_PAGES}")
    logging.info(f"Failed pages: {failed_pages}/{TOTAL_PAGES}")
    logging.info(f"{'='*60}\n")

    # Merge all results
    logging.info("Merging results...")
    merge_results()

    logging.info("Done!")

if __name__ == "__main__":
    main()
