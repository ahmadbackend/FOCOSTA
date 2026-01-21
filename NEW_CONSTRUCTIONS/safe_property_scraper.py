from curl_cffi import requests
from bs4 import BeautifulSoup
import json
import re
import logging
import time
import os
import random

# Set up logging with UTF-8 encoding
import sys

# Configure stdout to use UTF-8
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('safe_property_scraper.log', encoding='utf-8', errors='replace'),
        logging.StreamHandler(sys.stdout)
    ]
)

# Configuration - VERY SAFE SETTINGS
OUTPUT_DIR = "property_details"
FAILED_LOG = "failed_properties_safe.log"
MIN_DELAY = 10  # Minimum 10 seconds
MAX_DELAY = 15  # Maximum 15 seconds

# User agents
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
]

def get_tracking_phone(promotion_id, property_url):
    """Get real phone number from tracking-phone API using POST request"""
    try:
        tracking_url = f"https://web.gw.fotocasa.es/v1/promotions/{promotion_id}/tracking-phone"

        # POST payload
        payload = {
            "listingUrl": property_url,
            "marketplace": "FOTOCASA",
            "platform": "web",
            "userAgent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36"
        }

        headers = {
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9,ar-SA;q=0.8,ar;q=0.7',
            'Content-Type': 'application/json',
            'Origin': 'https://www.fotocasa.es',
            'Referer': property_url,
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36',
            'sec-ch-ua': '"Not(A:Brand";v="8", "Chromium";v="144", "Google Chrome";v="144"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-site'
        }

        response = requests.post(
            tracking_url,
            json=payload,
            headers=headers,
            impersonate="chrome120",
            timeout=30
        )

        if response.status_code == 200:
            data = response.json()
            # The response might contain the real phone number in different fields
            phone = data.get('phone') or data.get('phoneNumber') or data.get('trackingPhone')
            if phone:
                logging.info(f"Got tracking phone for promotion {promotion_id}: {phone}")
            return phone
        else:
            logging.warning(f"Failed to get tracking phone for {promotion_id}: HTTP {response.status_code}")
            return None
    except Exception as e:
        logging.error(f"Error fetching tracking phone for {promotion_id}: {str(e)}")
        return None

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
                        address = project.get('address', {})

                        # DEBUG: Log all phone-related fields
                        logging.info(f"Property {project.get('id')} - advertiser.phone: {advertiser.get('phone')}")

                        # Get realEstatePromotionId for tracking phone API
                        real_estate_detail = data.get('realEstatePromotionDetailEntityV2', {})
                        promotion_id = real_estate_detail.get('realEstatePromotionId')

                        # Try to get REAL phone from tracking API
                        tracking_phone = None
                        if promotion_id:
                            logging.info(f"Found promotion ID: {promotion_id}, fetching tracking phone...")
                            tracking_phone = get_tracking_phone(promotion_id, property_url)

                        # Try publisher phone as fallback
                        publisher_phone = None
                        if real_estate_detail:
                            publisher = real_estate_detail.get('publisher', {})
                            publisher_phone = publisher.get('phone')
                            logging.info(f"Property {project.get('id')} - publisher.phone: {publisher_phone}")

                        # Priority: tracking_phone > publisher_phone > advertiser.phone
                        phone_number = tracking_phone or publisher_phone or advertiser.get('phone')
                        logging.info(f"Final phone for property {project.get('id')}: {phone_number}")

                        property_data = {
                            'property_id': project.get('id'),
                            'property_url': property_url,
                            'scrape_date': time.strftime('%Y-%m-%dT%H:%M:%SZ'),
                            'title': project.get('name'),
                            'description': project.get('description', {}).get('es-ES', ''),

                            'contact_info': {
                                'phone_number': phone_number,
                                'advertiser_name': advertiser.get('promoterName'),
                                'client_id': advertiser.get('clientId'),
                            },

                            'location': {
                                'city': address.get('location', {}).get('level5'),
                                'province': address.get('location', {}).get('level2'),
                                'region': address.get('location', {}).get('level1'),
                                'country': address.get('location', {}).get('country'),
                                'latitude': address.get('coordinates', {}).get('latitude'),
                                'longitude': address.get('coordinates', {}).get('longitude'),
                            },

                            'details': {
                                'min_rooms': project.get('minRooms'),
                                'max_rooms': project.get('maxRooms'),
                                'min_bathrooms': project.get('minBathrooms'),
                                'max_bathrooms': project.get('maxBathrooms'),
                                'min_surface': project.get('minSurface'),
                                'max_surface': project.get('maxSurface'),
                                'min_price': project.get('minPrice'),
                                'max_price': project.get('maxPrice'),
                            },

                            'images': project.get('multimedias', {}).get('picture', []),
                            'videos': project.get('multimedias', {}).get('video', []),
                        }

                        # Add publisher website if available
                        publisher = project.get('realEstatePromotionDetailEntityV2', {}).get('publisher', {})
                        if publisher:
                            property_data['contact_info']['website'] = publisher.get('url')

                        return property_data

        return None
    except Exception as e:
        logging.error(f"Error extracting data: {e}")
        return None

def scrape_property_safe(property_url, property_id):
    """Scrape single property with NO PROXY and long delays"""

    try:
        # Random delay BEFORE request
        delay = random.uniform(MIN_DELAY, MAX_DELAY)
        logging.info(f"Waiting {delay:.1f} seconds before requesting property {property_id}...")
        time.sleep(delay)

        # Create session WITHOUT proxy
        session = requests.Session(impersonate="chrome120")

        headers = {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'Accept-Language': 'en-US,en;q=0.9,ar-SA;q=0.8,ar;q=0.7',
            'Cache-Control': 'max-age=0',
            'DNT': '1',
            'Referer': 'https://www.fotocasa.es/es/promociones-obra-nueva/comprar/viviendas/espana/todas-las-zonas/l',
            'sec-ch-ua': '"Not(A:Brand";v="8", "Chromium";v="144", "Google Chrome";v="144"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'document',
            'sec-fetch-mode': 'navigate',
            'sec-fetch-site': 'none',
            'sec-fetch-user': '?1',
            'Upgrade-Insecure-Requests': '1',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36'
        }

        logging.info(f"Requesting property {property_id}: {property_url}")
        response = session.get(property_url, headers=headers, timeout=45, allow_redirects=True)

        if response.status_code == 200:
            property_data = extract_property_data_from_html(response.text, property_url)

            if property_data:
                # Save to file
                output_file = f"{OUTPUT_DIR}/property_{property_id}.json"
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(property_data, f, ensure_ascii=False, indent=2)

                phone = property_data.get('contact_info', {}).get('phone_number', 'N/A')
                logging.info(f"SUCCESS: Property {property_id} - Phone: {phone}")
                return True
            else:
                logging.warning(f"NO DATA: Property {property_id}")
                with open(FAILED_LOG, 'a', encoding='utf-8', errors='surrogateescape') as f:
                    f.write(f"{property_id}|{property_url}|NO_DATA_FOUND\n")
                return False
        else:
            logging.error(f"HTTP {response.status_code}: Property {property_id}")
            with open(FAILED_LOG, 'a', encoding='utf-8', errors='surrogateescape') as f:
                f.write(f"{property_id}|{property_url}|HTTP_{response.status_code}\n")
            return False

    except Exception as e:
        error_msg = str(e).encode('utf-8', errors='replace').decode('utf-8')
        logging.error(f"ERROR: Property {property_id} - {error_msg}")
        with open(FAILED_LOG, 'a', encoding='utf-8', errors='surrogateescape') as f:
            f.write(f"{property_id}|{property_url}|{error_msg}\n")
        return False

def load_property_links():
    """Load property URLs from all_properties.json"""
    try:
        with open('all_properties.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
            properties = data.get('properties', [])

            property_list = []
            for prop in properties:
                url = prop.get('url')
                prop_id = prop.get('id')

                if url and (not prop_id or prop_id == 0):
                    match = re.search(r'/(\d+)$', url)
                    if match:
                        prop_id = match.group(1)

                if url and prop_id:
                    property_list.append({'url': url, 'id': str(prop_id)})

            return property_list
    except Exception as e:
        logging.error(f"Error loading properties: {e}")
        return []

def merge_results():
    """Merge all property JSON files and create CSV"""
    import glob
    import csv

    property_files = sorted(glob.glob(f"{OUTPUT_DIR}/property_*.json"))
    all_properties = []

    for pfile in property_files:
        try:
            with open(pfile, 'r', encoding='utf-8') as f:
                all_properties.append(json.load(f))
        except Exception as e:
            logging.error(f"Error reading {pfile}: {e}")

    # Save JSON
    with open('all_property_details.json', 'w', encoding='utf-8') as f:
        json.dump({
            'total': len(all_properties),
            'scrape_date': time.strftime('%Y-%m-%dT%H:%M:%SZ'),
            'properties': all_properties
        }, f, ensure_ascii=False, indent=2)

    # Save CSV
    with open('property_contacts.csv', 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Property ID', 'Title', 'Phone', 'Advertiser', 'City', 'Province', 'URL'])

        for prop in all_properties:
            writer.writerow([
                prop.get('property_id', ''),
                prop.get('title', ''),
                prop.get('contact_info', {}).get('phone_number', ''),
                prop.get('contact_info', {}).get('advertiser_name', ''),
                prop.get('location', {}).get('city', ''),
                prop.get('location', {}).get('province', ''),
                prop.get('property_url', '')
            ])

    logging.info(f"Merged {len(all_properties)} properties")

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    open(FAILED_LOG, 'w', encoding='utf-8').close()

    properties = load_property_links()

    if not properties:
        logging.error("No properties to scrape!")
        return

    logging.info(f"Starting SAFE scraping for {len(properties)} properties")
    logging.info(f"Delay: {MIN_DELAY}-{MAX_DELAY} seconds between requests")
    logging.info(f"NO PROXY - Using direct connection")
    logging.info(f"Single-threaded (one at a time)")
    logging.info(f"Estimated time: {len(properties) * ((MIN_DELAY + MAX_DELAY) / 2) / 60:.1f} minutes\n")

    successful = 0
    failed = 0
    start_time = time.time()

    for i, prop in enumerate(properties, 1):
        logging.info(f"\n[{i}/{len(properties)}] Processing property {prop['id']}...")

        if scrape_property_safe(prop['url'], prop['id']):
            successful += 1
        else:
            failed += 1

        # Progress report every 10 properties
        if i % 10 == 0:
            elapsed = time.time() - start_time
            rate = i / elapsed
            remaining = (len(properties) - i) / rate
            logging.info(f"Progress: {i}/{len(properties)} ({i/len(properties)*100:.1f}%)")
            logging.info(f"Success: {successful}, Failed: {failed}")
            logging.info(f"Estimated time remaining: {remaining/60:.1f} minutes")

    elapsed = time.time() - start_time
    logging.info(f"{'='*60}")
    logging.info(f"Scraping completed in {elapsed/60:.1f} minutes")
    logging.info(f"Successful: {successful}/{len(properties)}")
    logging.info(f"Failed: {failed}/{len(properties)}")
    logging.info(f"{'='*60}")

    if successful > 0:
        logging.info("Merging results...")
        merge_results()
        logging.info("Done! Check property_contacts.csv for phone numbers")

if __name__ == "__main__":
    main()
