import asyncio
import json
import logging
import os
from pathlib import Path
from typing import List, Dict
from playwright.async_api import async_playwright

PROXY_URL = "http://customer-AHMAD_NSPT0-cc-ES:fCpqqylS70igFo+j@es-pr.oxylabs.io:10000"
ALL_PROPERTIES_PATH = "G:/FOTOCASA/HOMES/all_properties.json"
PROGRESS_PATH = "G:/FOTOCASA/HOMES/playwright_progress.json"
OUTPUT_DIR = Path("G:/FOTOCASA/HOMES/playwright_results")
OUTPUT_DIR.mkdir(exist_ok=True)
BATCH_SIZE = int(os.environ.get("FC_BATCH_SIZE", 10))
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

class FotocasaScraper:
    def __init__(self):
        self.progress = self.load_progress()
        self.all_properties = self.load_all_properties()

    def load_progress(self):
        if os.path.exists(PROGRESS_PATH):
            with open(PROGRESS_PATH, 'r', encoding='utf-8') as f:
                return set(json.load(f))
        return set()

    def save_progress(self):
        with open(PROGRESS_PATH, 'w', encoding='utf-8') as f:
            json.dump(list(self.progress), f)

    def load_all_properties(self):
        with open(ALL_PROPERTIES_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)

    async def run(self):
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            tasks = []
            for batch in self.get_batches():
                results = await asyncio.gather(*[
                    self.scrape_property(browser, prop) for prop in batch
                ])
                for prop_id, data in results:
                    if data:
                        self.save_result(prop_id, data)
                        self.progress.add(prop_id)
                self.save_progress()
            await browser.close()

    def get_batches(self):
        to_process = [p for p in self.all_properties if str(p['id']) not in self.progress]
        for i in range(0, len(to_process), BATCH_SIZE):
            yield to_process[i:i+BATCH_SIZE]

    async def scrape_property(self, browser, prop):
        prop_id = str(prop['id'])
        url = prop['url']
        context = await browser.new_context(
            proxy={
                "server": "http://es-pr.oxylabs.io:10000",
                "username": "customer-AHMAD_NSPT0-cc-ES",
                "password": "fCpqqylS70igFo+j"
            },
            viewport=None
        )
        page = await context.new_page()
        try:
            await page.goto(url, timeout=120000)
            # Handle consent popup
            if await page.is_visible('#didomi-notice-agree-button'):
                await page.click('#didomi-notice-agree-button')
            await page.wait_for_selector('h1.re-DetailHeader-propertyTitle', timeout=30000)
            # Extract info
            data = await self.extract_info(page)
            # Click view phone and intercept
            phone = await self.get_phone_number(page, context)
            data['phone'] = phone
            await page.close()
            await context.close()
            return prop_id, data
        except Exception as e:
            logging.error(f"[FAILED] {prop_id}: {e}")
            await page.close()
            await context.close()
            return prop_id, None

    async def extract_info(self, page):
        data = {}
        data['title'] = await page.text_content('h1.re-DetailHeader-propertyTitle')
        data['location'] = await page.text_content('p.re-DetailHeader-municipalityTitle')
        data['price'] = await page.text_content('span.re-DetailHeader-price')
        data['description'] = await page.text_content('p.re-DetailDescription')
        data['images'] = [img.get_attribute('src') for img in await page.query_selector_all('img.re-DetailMosaicPhoto')]
        # Video: try to find video src if present
        video_btn = await page.query_selector('button[aria-label="Videos"]')
        data['video'] = None
        if video_btn:
            await video_btn.click()
            video = await page.query_selector('video source')
            if video:
                data['video'] = await video.get_attribute('src')
        # Advertiser
        adv = await page.query_selector('a.re-FormContactDetail-logo')
        data['advertiser'] = await adv.get_attribute('title') if adv else None
        return data

    async def get_phone_number(self, page, context):
        phone = None
        async def handle_route(route, request):
            nonlocal phone
            if 'tracking-phone' in request.url:
                response = await route.fetch()
                try:
                    json_data = await response.json()
                    phone = json_data.get('phone')
                except Exception:
                    pass
            await route.continue_()
        await context.route('**/tracking-phone', handle_route)
        btn = await page.query_selector('button[data-testid="view-phone-button"]')
        if btn:
            await btn.click()
            await asyncio.sleep(2)
        return phone

    def save_result(self, prop_id, data):
        with open(OUTPUT_DIR / f'{prop_id}.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

if __name__ == '__main__':
    scraper = FotocasaScraper()
    asyncio.run(scraper.run())
