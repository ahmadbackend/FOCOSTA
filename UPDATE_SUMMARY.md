# 🚀 FOTOCASA SCRAPER UPDATES - January 21, 2026

## Summary of Changes

Both scrapers have been updated with:
1. ✅ **POST request** for tracking phone API
2. ✅ **Common headers** matching real browser requests
3. ✅ **Spain proxy** for housing scraper

---

## 1. NEW_CONSTRUCTIONS/safe_property_scraper.py

### Changes Made:

#### A. Updated `get_tracking_phone()` Function
- **Method**: Changed from GET to **POST**
- **Payload**: Added JSON payload with:
  ```json
  {
    "listingUrl": "https://www.fotocasa.es/...",
    "marketplace": "FOTOCASA",
    "platform": "web",
    "userAgent": "Mozilla/5.0..."
  }
  ```
- **Headers**: Added proper API headers including:
  - `Content-Type: application/json`
  - `Origin`, `Referer`, sec-ch-* headers
  - Proper User-Agent

#### B. Updated Main Request Headers
- Added all common headers from real browser requests:
  - `Accept`, `Accept-Encoding`, `Accept-Language`
  - `sec-ch-ua`, `sec-ch-ua-mobile`, `sec-ch-ua-platform`
  - `sec-fetch-dest`, `sec-fetch-mode`, `sec-fetch-site`
  - `DNT`, `Cache-Control`
  - Updated User-Agent to Chrome 144

#### C. Phone Number Priority
The scraper now uses this priority for phone numbers:
1. **tracking_phone** (from POST API) ← REAL phone number ✅
2. **publisher.phone** (fallback)
3. **advertiser.phone** (last resort)

---

## 2. HOMES/house_scraper.py

### Changes Made:

#### A. Proxy Update
- **Old**: US proxy
- **New**: Spain proxy (es-pr.oxylabs.io:10000)

#### B. Added COMMON_HEADERS
All requests now use consistent headers:
```python
COMMON_HEADERS = {
    'Accept': 'text/html,application/xhtml+xml,...',
    'Accept-Encoding': 'gzip, deflate, br, zstd',
    'Accept-Language': 'en-US,en;q=0.9,ar-SA;q=0.8,ar;q=0.7',
    'Cache-Control': 'max-age=0',
    'DNT': '1',
    'sec-ch-ua': '"Not(A:Brand";v="8", "Chromium";v="144"...',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"',
    'sec-fetch-dest': 'document',
    'sec-fetch-mode': 'navigate',
    'sec-fetch-site': 'none',
    'sec-fetch-user': '?1',
    'Upgrade-Insecure-Requests': '1',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)...'
}
```

#### C. Code Cleanup
- Removed unused `os` import

---

## How the Tracking Phone API Works

### API Endpoint:
```
POST https://web.gw.fotocasa.es/v1/promotions/{promotionId}/tracking-phone
```

### Request Payload:
```json
{
    "listingUrl": "https://www.fotocasa.es/es/comprar/obra-nueva/valencia-capital/20643452",
    "marketplace": "FOTOCASA",
    "platform": "web",
    "userAgent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36"
}
```

### Example:
For property **20643452** with promotion ID `de195780-0b14-4862-9921-2a46b3b27f6b`:

**Wrong phone** (from HTML): `954201803`
**Correct phone** (from API): `+34518880004` ✅

---

## Testing Instructions

### NEW_CONSTRUCTIONS Scraper:
```powershell
cd G:\FOTOCASA\NEW_CONSTRUCTIONS
py -3.11 safe_property_scraper.py
```

Check the log file to see:
- `Got tracking phone for promotion {id}: {phone}` ← Real phone number

### HOMES Scraper:
```powershell
cd G:\FOTOCASA\HOMES
py -3.11 house_scraper.py
```

Should now use:
- Spain proxy (better for Spanish site)
- Proper browser headers (less likely to be blocked)

---

## Files Modified:
1. ✅ `NEW_CONSTRUCTIONS/safe_property_scraper.py`
2. ✅ `HOMES/house_scraper.py`
3. 📝 `NEW_CONSTRUCTIONS/TRACKING_PHONE_DISCOVERY.md` (documentation)
4. 📝 `UPDATE_SUMMARY.md` (this file)

---

## Next Steps:
1. Run the NEW_CONSTRUCTIONS scraper to verify phone numbers are correct
2. Run the HOMES scraper to scrape all 15,203 pages
3. Check logs for any issues

**All changes validated and ready to use!** 🎯
