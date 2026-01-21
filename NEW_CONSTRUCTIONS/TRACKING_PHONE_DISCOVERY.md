# 🎯 TRACKING PHONE API DISCOVERY

## Summary
We discovered that Fotocasa uses a separate API endpoint to provide the **REAL** phone number for property promotions, which is different from the phone number embedded in the HTML.

## The Problem
- Properties were showing phone numbers like `954201803` in the HTML data
- But the REAL phone number was actually `+34518880004`
- This is because Fotocasa uses "tracked" phone numbers that are revealed through an API call

## The Solution

### 1. **UUID Discovery**
Found in the HTML under `realEstatePromotionDetailEntityV2.realEstatePromotionId`:
```json
"realEstatePromotionId": "de195780-0b14-4862-9921-2a46b3b27f6b"
```

### 2. **API Endpoint**
```
https://web.gw.fotocasa.es/v1/promotions/{realEstatePromotionId}/tracking-phone
```

### 3. **Implementation**
The scraper now:
1. Extracts `realEstatePromotionId` from the `__INITIAL_PROPS__` JSON
2. Calls the tracking-phone API: `https://web.gw.fotocasa.es/v1/promotions/{id}/tracking-phone`
3. Gets the REAL phone number from the API response
4. Falls back to publisher.phone or advertiser.phone if API fails

### 4. **Phone Number Priority**
```
tracking_phone (from API) > publisher.phone > advertiser.phone
```

## Example

For property **20643452** (VERA I project):
- **promotionId**: `de195780-0b14-4862-9921-2a46b3b27f6b`
- **advertiser.phone**: `954201803` (WRONG!)
- **tracking API URL**: `https://web.gw.fotocasa.es/v1/promotions/de195780-0b14-4862-9921-2a46b3b27f6b/tracking-phone`
- **REAL phone**: `+34518880004` ✅

## Files Modified
- `safe_property_scraper.py`: Added `get_tracking_phone()` function and updated phone extraction logic

## Next Steps
Run the scraper to test if the tracking phone API returns the correct phone numbers!
