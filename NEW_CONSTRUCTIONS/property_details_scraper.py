from curl_cffi import requests
from bs4 import BeautifulSoup
import json
import re
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import threading
import os

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(threadName)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('property_details_scraper.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

# Configuration
MAX_THREADS = 30
PROXY_URL = "http://customer-AHMAD_NSPT0-cc-US:fCpqqylS70igFo+j@us-pr.oxylabs.io:10000"
OUTPUT_DIR = "property_details"
FAILED_LOG = "failed_properties.log"
DELAY_BETWEEN_REQUESTS = 2  # seconds

# Thread-safe counters and lock
lock = threading.Lock()
successful_properties = 0
failed_properties = 0
request_times = []

def get_session_with_proxy():
    """Create a session with proxy that rotates by session"""
    session = requests.Session(impersonate="chrome110")
    session.proxies = {
        "http": PROXY_URL,
        "https": PROXY_URL
    }
    return session

def rate_limit():
    """Ensure minimum delay between requests"""
    with lock:
        current_time = time.time()
        # Remove old timestamps (older than delay period)
        request_times[:] = [t for t in request_times if current_time - t < DELAY_BETWEEN_REQUESTS]

        # If we have recent requests, wait
        if request_times:
            time_since_last = current_time - request_times[-1]
            if time_since_last < DELAY_BETWEEN_REQUESTS:
                wait_time = DELAY_BETWEEN_REQUESTS - time_since_last
                time.sleep(wait_time)

        # Record this request time
        request_times.append(time.time())

def extract_property_data(html_content, property_url):
    """Extract all property data from HTML"""
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

                        # Extract projectDetail if exists
                        if 'projectDetail' in data:
                            project = data['projectDetail']
                            real_estate = project.get('realEstate', {})
                            advertiser = project.get('advertiser', {})
                            address = project.get('address', {})

                            # Build comprehensive property data
                            property_data = {
                                'property_id': project.get('id'),
                                'property_url': property_url,
                                'scrape_date': time.strftime('%Y-%m-%dT%H:%M:%SZ'),

                                'basic_info': {
                                    'title': project.get('name'),
                                    'property_type': real_estate.get('buildingType'),
                                    'transaction_type': 'Buy (New Construction)',
                                    'is_new_construction': real_estate.get('isNewConstruction', True),
                                    'creation_date': project.get('realEstatePromotionDetailEntityV2', {}).get('creationDate'),
                                    'alter_date': project.get('realEstatePromotionDetailEntityV2', {}).get('alterDate'),
                                },

                                'location': {
                                    'full_address': f"{address.get('location', {}).get('level5', '')}, {address.get('location', {}).get('level4', '')}, {address.get('location', {}).get('level2', '')}, {address.get('location', {}).get('level1', '')}, {address.get('location', {}).get('country', '')}".strip(', '),
                                    'country': address.get('location', {}).get('country'),
                                    'region': address.get('location', {}).get('level1'),
                                    'province': address.get('location', {}).get('level2'),
                                    'county': address.get('location', {}).get('level3'),
                                    'city': address.get('location', {}).get('level5'),
                                    'district': address.get('location', {}).get('level4'),
                                    'zip_code': project.get('realEstatePromotionDetailEntityV2', {}).get('address', {}).get('zipCode'),
                                    'coordinates': {
                                        'latitude': address.get('coordinates', {}).get('latitude'),
                                        'longitude': address.get('coordinates', {}).get('longitude'),
                                    }
                                },

                                'price': {
                                    'min_price': project.get('minPrice', 0),
                                    'max_price': project.get('maxPrice', 0),
                                    'display': 'Contact for price' if project.get('minPrice', 0) == 0 else f"€{project.get('minPrice', 0):,}",
                                },

                                'property_details': {
                                    'rooms': {
                                        'min': project.get('minRooms'),
                                        'max': project.get('maxRooms'),
                                    },
                                    'bathrooms': {
                                        'min': project.get('minBathrooms'),
                                        'max': project.get('maxBathrooms'),
                                    },
                                    'surface_m2': {
                                        'min': project.get('minSurface'),
                                        'max': project.get('maxSurface'),
                                    },
                                    'units': []
                                },

                                'energy_certificate': {
                                    'certificate_type': project.get('energyCertificate', {}).get('energyPerformanceCertificateTypeId'),
                                    'energy_efficiency_rating': project.get('energyCertificate', {}).get('energyEfficiencyRatingTypeId'),
                                    'energy_efficiency_value': project.get('energyCertificate', {}).get('energyEfficiencyValue'),
                                    'environment_impact_rating': project.get('energyCertificate', {}).get('environmentImpactRatingTypeId'),
                                    'environment_impact_value': project.get('energyCertificate', {}).get('environmentImpactValue'),
                                },

                                'features': [],

                                'description': project.get('description', {}).get('es-ES', ''),

                                'advertiser': {
                                    'client_id': advertiser.get('clientId'),
                                    'name': advertiser.get('promoterName'),
                                    'phone': advertiser.get('phone'),
                                    'logo_url': advertiser.get('logo', {}).get('url') if isinstance(advertiser.get('logo'), dict) else None,
                                    'type': 'professional' if project.get('clientType') == 3 else 'private',
                                },

                                'multimedia': {
                                    'images': [],
                                    'videos': [],
                                },

                                'contact_info': {
                                    'phone_number': advertiser.get('phone'),
                                    'is_tracked_phone': real_estate.get('isTrackedPhone'),
                                    'contact_name': advertiser.get('promoterName'),
                                    'website': None,
                                },

                                'metadata': {
                                    'is_premium': real_estate.get('isPremium', False),
                                    'is_opportunity': real_estate.get('isOpportunity', False),
                                    'is_new': real_estate.get('isNew', False),
                                    'is_virtual_tour': real_estate.get('isVirtualTour', False),
                                    'has_microsite': real_estate.get('hasMicrosite', False),
                                }
                            }

                            # Extract units
                            units = project.get('units', [])
                            for unit in units:
                                property_data['property_details']['units'].append({
                                    'unit_id': unit.get('id'),
                                    'reference': unit.get('agencyReference'),
                                    'rooms': unit.get('rooms'),
                                    'bathrooms': unit.get('baths'),
                                    'surface_m2': unit.get('surface'),
                                    'price': unit.get('transactions', [{}])[0].get('price', 0) if unit.get('transactions') else 0,
                                    'extras': [extra.get('keyName') for extra in unit.get('extras', [])],
                                })

                            # Extract features from first unit or project
                            if units and units[0].get('extras'):
                                property_data['features'] = [extra.get('keyName') for extra in units[0].get('extras', [])]

                            # Extract multimedia
                            multimedias = project.get('multimedias', {})
                            if 'picture' in multimedias:
                                property_data['multimedia']['images'] = multimedias['picture']
                            if 'video' in multimedias:
                                property_data['multimedia']['videos'] = multimedias['video']

                            # Extract publisher info
                            publisher = project.get('realEstatePromotionDetailEntityV2', {}).get('publisher', {})
                            if publisher:
                                property_data['advertiser']['website'] = publisher.get('url')
                                property_data['contact_info']['website'] = publisher.get('url')

                            return property_data

                        logging.warning(f"No projectDetail found in data for {property_url}")
                        return None

                    except json.JSONDecodeError as e:
                        logging.error(f"JSON decode error for {property_url}: {e}")
                        return None

        logging.warning(f"No __INITIAL_PROPS__ found for {property_url}")
        return None

    except Exception as e:
        logging.error(f"Error extracting data from {property_url}: {e}")
        return None

def scrape_property(property_url, property_id):
    """Scrape a single property page"""
    global successful_properties, failed_properties

    # Rate limiting
    rate_limit()

    try:
        # Create a new session for each request (new IP)
        session = get_session_with_proxy()

        logging.info(f"Scraping property {property_id}: {property_url}")

        # Add headers to mimic browser with random user agent
        import random
        headers = {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'es-ES,es;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Cache-Control': 'max-age=0',
            'Sec-Ch-Ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"Windows"',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Upgrade-Insecure-Requests': '1',
            'Referer': 'https://www.fotocasa.es/es/promociones-obra-nueva/comprar/viviendas/espana/todas-las-zonas/l',
        }

        response = session.get(property_url, headers=headers, timeout=45, allow_redirects=True)
        response.raise_for_status()

        # Extract property data
        property_data = extract_property_data(response.text, property_url)

        if property_data:
            # Save to individual file
            output_file = f"{OUTPUT_DIR}/property_{property_id}.json"
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(property_data, f, ensure_ascii=False, indent=2)

            with lock:
                successful_properties += 1

            phone = property_data.get('advertiser', {}).get('phone', 'N/A')
            logging.info(f"[SUCCESS] Property {property_id}: Phone={phone}")
            return {'success': True, 'property_id': property_id, 'phone': phone}
        else:
            with lock:
                failed_properties += 1
            with open(FAILED_LOG, 'a', encoding='utf-8') as f:
                f.write(f"Property {property_id} ({property_url}): No data extracted\n")
            logging.warning(f"[NO DATA] Property {property_id}: No data extracted")
            return {'success': False, 'property_id': property_id, 'error': 'No data extracted'}

    except Exception as e:
        with lock:
            failed_properties += 1
        error_msg = str(e)
        logging.error(f"[ERROR] Property {property_id}: {error_msg}")
        with open(FAILED_LOG, 'a', encoding='utf-8') as f:
            f.write(f"Property {property_id} ({property_url}): {error_msg}\n")
        return {'success': False, 'property_id': property_id, 'error': error_msg}

def load_property_links():
    """Load property links from all_properties.json"""
    try:
        with open('all_properties.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
            properties = data.get('properties', [])

            # Extract URL and ID
            property_list = []
            for prop in properties:
                url = prop.get('url')
                prop_id = prop.get('id')

                # If ID is 0 or None, extract from URL
                if url and (not prop_id or prop_id == 0):
                    # Extract ID from URL (last part after /)
                    match = re.search(r'/(\d+)$', url)
                    if match:
                        prop_id = match.group(1)

                if url and prop_id:
                    property_list.append({'url': url, 'id': str(prop_id)})

            return property_list
    except FileNotFoundError:
        logging.error("all_properties.json not found!")
        return []
    except Exception as e:
        logging.error(f"Error loading property links: {e}")
        return []

def merge_all_properties():
    """Merge all individual property JSON files into one"""
    import glob

    all_properties = []

    # Read all property files
    property_files = sorted(glob.glob(f"{OUTPUT_DIR}/property_*.json"))

    for property_file in property_files:
        try:
            with open(property_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                all_properties.append(data)
        except Exception as e:
            logging.error(f"Error reading {property_file}: {e}")

    # Save merged results
    output_file = "all_property_details.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            'total_properties': len(all_properties),
            'scrape_date': time.strftime('%Y-%m-%dT%H:%M:%SZ'),
            'properties': all_properties
        }, f, ensure_ascii=False, indent=2)

    logging.info(f"Merged {len(all_properties)} properties into {output_file}")

    # Create a CSV with key info
    csv_file = "property_contacts.csv"
    with open(csv_file, 'w', encoding='utf-8', newline='') as f:
        import csv
        writer = csv.writer(f)
        writer.writerow(['Property ID', 'Title', 'Phone', 'Advertiser', 'Location', 'Price', 'URL'])

        for prop in all_properties:
            writer.writerow([
                prop.get('property_id', ''),
                prop.get('basic_info', {}).get('title', ''),
                prop.get('contact_info', {}).get('phone_number', ''),
                prop.get('advertiser', {}).get('name', ''),
                prop.get('location', {}).get('city', ''),
                prop.get('price', {}).get('display', ''),
                prop.get('property_url', '')
            ])

    logging.info(f"Created {csv_file} with property contacts")

def main():
    # Create output directory
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Clear failed log
    open(FAILED_LOG, 'w', encoding='utf-8').close()

    # Load property links
    properties = load_property_links()

    if not properties:
        logging.error("No properties to scrape!")
        return

    logging.info(f"Starting property details scraper for {len(properties)} properties with {MAX_THREADS} threads")
    logging.info(f"Rate limit: {DELAY_BETWEEN_REQUESTS} seconds between requests")

    start_time = time.time()

    # Use ThreadPoolExecutor for concurrent scraping
    with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
        # Submit all properties
        futures = {
            executor.submit(scrape_property, prop['url'], prop['id']): prop
            for prop in properties
        }

        # Process completed tasks
        for future in as_completed(futures):
            prop = futures[future]
            try:
                result = future.result()
                if result['success']:
                    logging.info(f"[SUCCESS] Property {result['property_id']}: Phone={result.get('phone', 'N/A')}")
                else:
                    logging.error(f"[FAILED] Property {result['property_id']}: {result.get('error', 'Unknown error')}")
            except Exception as e:
                logging.error(f"Exception for property {prop['id']}: {e}")

    elapsed_time = time.time() - start_time

    logging.info(f"\n{'='*60}")
    logging.info(f"Scraping completed in {elapsed_time:.2f} seconds")
    logging.info(f"Successful properties: {successful_properties}/{len(properties)}")
    logging.info(f"Failed properties: {failed_properties}/{len(properties)}")
    logging.info(f"{'='*60}\n")

    # Merge all results
    logging.info("Merging results...")
    merge_all_properties()

    logging.info("Done! Check:")
    logging.info("  - all_property_details.json (full data)")
    logging.info("  - property_contacts.csv (phone numbers)")
    logging.info("  - failed_properties.log (failed properties)")

if __name__ == "__main__":
    main()
