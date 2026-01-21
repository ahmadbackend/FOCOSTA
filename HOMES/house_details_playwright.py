import asyncio
import json
import os
import logging
from typing import List, Dict, Any
from playwright.async_api import async_playwright

# Configuration
PROXY_URL = "http://customer-AHMAD_NSPT0-cc-ES:fCpqqylS70igFo+j@es-pr.oxylabs.io:10000"
MAX_CONCURRENT = 20  # Number of concurrent browsers
BATCH_SIZE = 20
OUTPUT_DIR = "house_details"
FAILED_LOG = "failed_houses.log"
ALL_PROPERTIES_PATH = "all_properties.json"
MAX_RETRIES = 3
RESUME = True  # Enable resume support

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('house_details_playwright.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)


def get_already_scraped_ids():
    # Resume support: collect already scraped property ids
    scraped = set()
    if os.path.exists(OUTPUT_DIR):
        for fname in os.listdir(OUTPUT_DIR):
            if fname.startswith("house_") and fname.endswith(".json"):
                try:
                    pid = fname.split("_")[1].split(".")[0]
                    scraped.add(pid)
                except Exception:
                    continue
    return scraped

async def safe_text(page, selector, timeout=10000):
    try:
        el = await page.wait_for_selector(selector, timeout=timeout)
        return (await el.inner_text()).strip()
    except:
        return None

def load_properties(path: str) -> List[Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
        # Support both list and dict with 'properties' key
        if isinstance(data, dict) and 'properties' in data:
            return data['properties']
        return data

async def scrape_batch(batch: List[Dict[str, Any]], batch_start_idx: int, total: int, scraped_ids):
    sem = asyncio.Semaphore(MAX_CONCURRENT)
    tasks = []
    for idx, prop in enumerate(batch):
        url = prop.get('url')
        prop_id = str(prop.get('id'))
        out_path = os.path.join(OUTPUT_DIR, f"house_{prop_id}.json")
        global_idx = batch_start_idx + idx + 1
        if url and prop_id:
            if RESUME and prop_id in scraped_ids:
                logging.info(f"[{global_idx}/{total}] Skipping property {prop_id} (already scraped)")
                continue
            logging.info(f"[{global_idx}/{total}] Processing property {prop_id}...")
            tasks.append(scrape_with_semaphore(sem, url, prop_id, global_idx, total))
    await asyncio.gather(*tasks)

async def scrape_with_semaphore(sem, url, prop_id, idx, total):
    async with sem:
        await scrape_property(url, prop_id, idx, total)

async def scrape_property(url: str, prop_id: str, idx: int, total: int):
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=False,
                                                  args=[
                                                      "--no-sandbox",
                                                      "--disable-setuid-sandbox",
                                                      "--disable-gpu",
                                                      "--disable-dev-shm-usage"
                                                  ]
                                                  )
                context = await browser.new_context(
                    no_viewport=True,
                    proxy={
                        "server": "http://pr.oxylabs.io:7777",
                        "username": "customer-AHMAD_NSPT0-cc-US",
                        "password": "Thvqz3aTY=0xiuH"
                    },
                )
                page = await context.new_page()
                phone_number = None
                network_response = None

                async def handle_response(response):
                    nonlocal phone_number, network_response
                    if "/tracking-phone" in response.url and response.request.method == "POST":
                        try:
                            data = await response.json()
                            phone_number = data.get("phone") or data.get("phoneNumber")
                            network_response = data
                        except Exception:
                            pass

                page.on("response", handle_response)
                try:
                    await page.goto(url, timeout=90000)
                    # Handle consent popup
                    try:
                        if await page.is_visible('#didomi-notice-agree-button'):
                            await page.click('#didomi-notice-agree-button')
                            await asyncio.sleep(1)
                    except Exception:
                        pass
                    await safe_text(page, '.re-ContentDetail')  # Wait for main content
                except Exception as e:
                    logging.error(f"[{idx}/{total}] [FAILED] {prop_id}: {e}")
                    await context.close()
                    await browser.close()
                    continue

                # --- FIXED SELECTORS BASED ON single_property_content.html ---
                # Description
                description = await  safe_text(page, 'p.re-DetailDescription')
                # Advertiser name (logo link title attribute)
                advertiser_name = await safe_text(page, '.re-FormContactDetailDown-client h4')


                # Images
                images = await page.eval_on_selector_all(
                    "div.re-DetailMosaic img",
                    "els => els.map(e => e.src).filter(Boolean)"
                )
                # Videos
                videos = await page.eval_on_selector_all(
                    '.re-ContentDetail video source',
                    'els => els.map(e => e.src).filter(Boolean)'
                )
                # Title
                title = await safe_text(page, 'main.re-ContentDetail h1.re-DetailHeader-propertyTitle')
                # Price
                price = await safe_text(page, 'main.re-ContentDetail span.re-DetailHeader-price')
                # Location
                location = await safe_text(page, 'main.re-ContentDetail p.re-DetailHeader-municipalityTitle')

                # Click "View telephone" button (fixed selector)
                try:
                    btn = await page.query_selector('button[data-testid="view-phone-button"], button[data-testid="card-call-tracking-phone"]')
                    if btn:
                        await btn.click()
                        await asyncio.sleep(2)
                except Exception as e:
                    logging.warning(f"Property {prop_id}: Could not click phone button: {e}")

                await asyncio.sleep(2)

                result = {
                    "property_id": prop_id,
                    "property_url": url,
                    "title": title,
                    "description": description,
                    "advertiser_name": advertiser_name,
                    "images": images,
                    "videos": videos,
                    "price": price,
                    "location": location,
                    "phone_number": phone_number,
                    "tracking_phone_response": network_response
                }
                print(result)
                if result["tracking_phone_response"]  :

                    out_path = os.path.join(OUTPUT_DIR, f"house_{prop_id}.json")
                    with open(out_path, "w", encoding="utf-8") as f:
                        json.dump(result, f, ensure_ascii=False, indent=2)
                    logging.info(f"[{idx}/{total}] [SUCCESS] {prop_id} - Phone: {phone_number}")
                    await context.close()
                    await browser.close()
                else:
                    logging.error(f"[{idx}/{total}] [FAILED] {prop_id}- {url} - No phone number found")
                return
        except Exception as e:
            logging.error(f"[{idx}/{total}] [FAILED] {prop_id} (attempt {attempt}): {e}")
            await asyncio.sleep(2)
    with open(FAILED_LOG, "a", encoding="utf-8") as f:
        f.write(f"{prop_id}\t{url}\tFAILED after {MAX_RETRIES} attempts\n")

async def main():
    properties = load_properties(ALL_PROPERTIES_PATH)
    if not properties:
        logging.error("No properties to scrape!")
        return
    scraped_ids = get_already_scraped_ids() if RESUME else set()
    total = len(properties)
    for batch_start in range(0, total, BATCH_SIZE):
        batch = properties[batch_start:batch_start+BATCH_SIZE]
        await scrape_batch(batch, batch_start, total, scraped_ids)
        logging.info(f"Batch {batch_start//BATCH_SIZE+1} completed.")

if __name__ == "__main__":
    asyncio.run(main())
