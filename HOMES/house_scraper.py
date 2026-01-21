#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fotocasa Housing Scraper - 15,203 pages with resume support
Multi-threaded with 20 workers and proxy rotation
"""

import json
import logging
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
import re

from bs4 import BeautifulSoup
from curl_cffi import requests

# ============ CONFIGURATION ============
TOTAL_PAGES = 15203
MAX_WORKERS = 20
DELAY_BETWEEN_BATCHES = 3  # seconds
PROXY_URL = "http://customer-AHMAD_NSPT0-cc-ES:fCpqqylS70igFo+j@es-pr.oxylabs.io:10000"
BASE_URL = "https://www.fotocasa.es/es/comprar/viviendas/espana/todas-las-zonas/l"

# Directories
OUTPUT_DIR = Path("G:/FOTOCASA/HOMES/pages")
FINAL_FILE = Path("G:/FOTOCASA/HOMES/all_properties.json")
LOG_FILE = Path("G:/FOTOCASA/HOMES/scraper.log")
ERROR_LOG = Path("G:/FOTOCASA/HOMES/failed_pages.log")
PROGRESS_FILE = Path("G:/FOTOCASA/HOMES/progress.json")

# Create directories
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Common headers for all requests
COMMON_HEADERS = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
    'Accept-Encoding': 'gzip, deflate, br, zstd',
    'Accept-Language': 'en-US,en;q=0.9,ar-SA;q=0.8,ar;q=0.7',
    'Cache-Control': 'max-age=0',
    'DNT': '1',
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

# ============ LOGGING SETUP ============
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(threadName)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# ============ PROGRESS TRACKING ============
def load_progress():
    """Load progress from file to resume scraping"""
    if PROGRESS_FILE.exists():
        try:
            with open(PROGRESS_FILE, 'r', encoding='utf-8') as f:
                progress = json.load(f)
                logger.info(f"Resuming from page {progress.get('last_page', 1)}")
                return set(progress.get('completed_pages', []))
        except Exception as e:
            logger.warning(f"Could not load progress: {e}")
    return set()

def save_progress(completed_pages):
    """Save progress to file"""
    try:
        with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
            json.dump({
                'completed_pages': list(completed_pages),
                'last_page': max(completed_pages) if completed_pages else 0,
                'total_pages': TOTAL_PAGES,
                'timestamp': datetime.now().isoformat()
            }, f, indent=2)
    except Exception as e:
        logger.error(f"Could not save progress: {e}")

# ============ SCRAPING FUNCTIONS ============
def get_page_url(page_num):
    """Generate URL for a given page number"""
    if page_num == 1:
        return BASE_URL
    return f"{BASE_URL}/{page_num}"

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

def scrape_page(page_num, session_id):
    """Scrape a single page"""
    url = get_page_url(page_num)
    output_file = OUTPUT_DIR / f"page_{page_num:05d}.json"

    # Skip if already scraped
    if output_file.exists():
        logger.info(f"Page {page_num} already scraped, skipping")
        return {
            'page': page_num,
            'success': True,
            'properties': 0,
            'skipped': True
        }

    try:
        logger.info(f"Scraping page {page_num}: {url}")

        # Make request with proxy
        response = requests.get(
            url,
            proxies={'http': PROXY_URL, 'https': PROXY_URL},
            timeout=30,
            impersonate="chrome110",
            headers=COMMON_HEADERS
        )

        if response.status_code != 200:
            logger.error(f"Page {page_num} returned status {response.status_code}")
            return {
                'page': page_num,
                'success': False,
                'error': f"HTTP {response.status_code}"
            }

        # Extract properties
        properties = extract_property_links(response.text)

        if not properties:
            logger.warning(f"Page {page_num} has 0 properties")

        # Save to individual file
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump({
                'page': page_num,
                'url': url,
                'scrape_date': datetime.now().isoformat(),
                'property_count': len(properties),
                'properties': properties
            }, f, ensure_ascii=False, indent=2)

        logger.info(f"Page {page_num} saved with {len(properties)} properties")

        return {
            'page': page_num,
            'success': True,
            'properties': len(properties)
        }

    except Exception as e:
        logger.error(f"Page {page_num} failed: {e}")
        # Log to error file
        with open(ERROR_LOG, 'a', encoding='utf-8') as f:
            f.write(f"{page_num},{url},{str(e)},{datetime.now().isoformat()}\n")

        return {
            'page': page_num,
            'success': False,
            'error': str(e)
        }

def merge_all_pages():
    """Merge all individual page files into one final JSON"""
    logger.info("Merging all pages into final JSON...")

    all_properties = []
    page_files = sorted(OUTPUT_DIR.glob("page_*.json"))

    for page_file in page_files:
        try:
            with open(page_file, 'r', encoding='utf-8') as f:
                page_data = json.load(f)
                all_properties.extend(page_data.get('properties', []))
        except Exception as e:
            logger.error(f"Error reading {page_file}: {e}")

    # Save merged file
    with open(FINAL_FILE, 'w', encoding='utf-8') as f:
        json.dump({
            'total_properties': len(all_properties),
            'scrape_date': datetime.now().isoformat(),
            'properties': all_properties
        }, f, ensure_ascii=False, indent=2)

    logger.info(f"Merged {len(all_properties)} properties into {FINAL_FILE}")
    return len(all_properties)

# ============ MAIN SCRAPER ============
def main():
    logger.info(f"Starting scraper for {TOTAL_PAGES} pages with {MAX_WORKERS} threads")

    # Load progress
    completed_pages = load_progress()

    # Create error log header if needed
    if not ERROR_LOG.exists():
        with open(ERROR_LOG, 'w', encoding='utf-8') as f:
            f.write("page,url,error,timestamp\n")

    # Determine pages to scrape
    all_pages = set(range(1, TOTAL_PAGES + 1))
    pages_to_scrape = sorted(all_pages - completed_pages)

    if not pages_to_scrape:
        logger.info("All pages already scraped!")
        merge_all_pages()
        return

    logger.info(f"Pages to scrape: {len(pages_to_scrape)}/{TOTAL_PAGES}")

    # Process in batches of MAX_WORKERS
    total_properties = 0
    successful = 0
    failed = 0

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        batch_num = 0

        for i in range(0, len(pages_to_scrape), MAX_WORKERS):
            batch = pages_to_scrape[i:i + MAX_WORKERS]
            batch_num += 1

            logger.info(f"Processing batch {batch_num} with {len(batch)} pages")

            # Submit batch
            future_to_page = {
                executor.submit(scrape_page, page, f"worker_{idx}"): page
                for idx, page in enumerate(batch)
            }

            # Collect results
            for future in as_completed(future_to_page):
                page = future_to_page[future]
                try:
                    result = future.result()

                    if result['success']:
                        successful += 1
                        if not result.get('skipped'):
                            total_properties += result.get('properties', 0)
                        completed_pages.add(page)
                        logger.info(f"Page {page} completed ({successful} successful, {failed} failed)")
                    else:
                        failed += 1
                        logger.error(f"Page {page} failed: {result.get('error', 'Unknown')}")

                except Exception as e:
                    failed += 1
                    logger.error(f"Page {page} exception: {e}")

            # Save progress after each batch
            save_progress(completed_pages)

            # Delay between batches (except for last batch)
            if i + MAX_WORKERS < len(pages_to_scrape):
                logger.info(f"Waiting {DELAY_BETWEEN_BATCHES} seconds before next batch...")
                time.sleep(DELAY_BETWEEN_BATCHES)

    # Final summary
    logger.info("="*60)
    logger.info(f"Scraping completed!")
    logger.info(f"Successful: {successful}")
    logger.info(f"Failed: {failed}")
    logger.info(f"Total properties: {total_properties}")
    logger.info("="*60)

    # Merge all pages
    if successful > 0:
        total = merge_all_pages()
        logger.info(f"Final merged file has {total} properties")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Scraping interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
