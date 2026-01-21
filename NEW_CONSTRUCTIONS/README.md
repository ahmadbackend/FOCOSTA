# Fotocasa Property Scraper

This scraper extracts property links from Fotocasa.es using multithreading and rotating proxies.

## Features

- ✅ Scrapes all 43 pages of property listings
- ✅ Uses 30 concurrent threads for faster scraping
- ✅ Rotating proxies (each thread uses a different IP from Oxylabs)
- ✅ Extracts both regular properties and new construction promotions
- ✅ Saves each page to a separate JSON file to avoid corruption
- ✅ Merges all results into a single JSON file
- ✅ Creates a simple text file with all property URLs
- ✅ Logs failed pages for retry
- ✅ Thread-safe operation with proper locking

## Installation

```bash
pip install beautifulsoup4
pip install curl_cffi
```

## Usage

```bash
py -3.11 new_construct_scraper.py
```

## Output Files

1. **output/page_001.json** to **output/page_043.json** - Individual page results
2. **all_properties.json** - Merged results with all properties
3. **property_links.txt** - Simple text file with one URL per line
4. **scraper.log** - Detailed execution log
5. **failed_pages.log** - List of failed pages to retry

## Configuration

Edit these variables in `new_construct_scraper.py`:

- `TOTAL_PAGES = 43` - Number of pages to scrape
- `MAX_THREADS = 30` - Number of concurrent threads
- `PROXY_URL` - Your Oxylabs proxy credentials

## How It Works

1. **Page Scraping**: Each thread scrapes a different page concurrently
2. **Proxy Rotation**: Each request uses the Oxylabs proxy which rotates IP by session
3. **Data Extraction**: Parses the `window.__INITIAL_PROPS__` JSON from the HTML
4. **Data Saving**: Each page result is saved immediately to avoid data loss
5. **Merging**: After all pages are scraped, results are merged into a single file

## Property Data Extracted

Each property includes:
- `url` - Full property URL
- `id` - Property ID
- `price` - Raw price value
- `location` - Property location
- `type` - "realEstate" or "promotion"
- `promotionTitle` - (for new constructions only)

## Example Output

```json
{
  "total_properties": 1234,
  "properties": [
    {
      "url": "https://www.fotocasa.es/es/comprar/vivienda/sevilla-capital/...",
      "id": 188269927,
      "price": 440000,
      "location": "San Lorenzo",
      "type": "realEstate"
    },
    ...
  ]
}
```

## Troubleshooting

- If pages fail, check `failed_pages.log`
- Reduce `MAX_THREADS` if you get connection errors
- Check proxy status if all requests fail
- Logs are written to both console and `scraper.log`
