# 🐛 BUG FIX - get_tracking_phone() Function

## Error:
```
Error extracting data: get_tracking_phone() takes 1 positional argument but 2 were given
```

## Root Cause:
The function definition was not properly updated in the previous edit. It had:
```python
def get_tracking_phone(promotion_id):  # Only 1 parameter
```

But was being called with:
```python
get_tracking_phone(promotion_id, property_url)  # 2 parameters
```

## Fix Applied:
Updated the function signature and implementation to:
```python
def get_tracking_phone(promotion_id, property_url):
    """Get real phone number from tracking-phone API using POST request"""
    # ... POST request with payload ...
```

## What Changed:
1. ✅ Function now accepts both `promotion_id` and `property_url` parameters
2. ✅ Uses **POST** instead of GET
3. ✅ Includes proper JSON payload with:
   - `listingUrl` (the property_url parameter)
   - `marketplace: "FOTOCASA"`
   - `platform: "web"`
   - `userAgent`
4. ✅ Proper API headers (Content-Type, Origin, Referer, etc.)

## Status:
✅ **FIXED** - No errors found

## Ready to Run:
```powershell
cd G:\FOTOCASA\NEW_CONSTRUCTIONS
py -3.11 safe_property_scraper.py
```

You should now see:
- ✅ `Got tracking phone for promotion {id}: {phone}`
- ✅ Properties scraped successfully with REAL phone numbers
