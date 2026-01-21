# Property Details Scraper

This scraper extracts complete property information including **phone numbers** from all property URLs collected earlier.

## Features

✅ **Extracts Phone Numbers** - Primary goal achieved!  
✅ Multithreaded (30 concurrent threads with rotating IPs)  
✅ Rate limiting (2 seconds between requests to avoid server overload)  
✅ Comprehensive data extraction (42+ fields per property)  
✅ Individual file saving to prevent data loss  
✅ Automatic merging into single JSON  
✅ CSV export with contact information  
✅ Failed property logging for retry  

## Prerequisites

```bash
pip install beautifulsoup4
pip install curl_cffi
```

## Usage

```bash
cd G:\FOTOCASA\NEW_CONSTRUCTIONS
py -3.11 property_details_scraper.py
```

## Input

Reads from: `all_properties.json` (created by new_construct_scraper.py)

## Output Files

1. **property_details/** - Individual JSON files for each property
   - `property_{id}.json` - One file per property

2. **all_property_details.json** - Merged complete dataset
   - All properties in one file
   - Full information for each property

3. **property_contacts.csv** - Spreadsheet with key info
   - Property ID
   - Title
   - **Phone Number** ⭐
   - Advertiser Name
   - Location
   - Price
   - URL

4. **property_details_scraper.log** - Execution log
   - Detailed scraping progress
   - Success/failure status
   - Phone numbers found

5. **failed_properties.log** - Failed properties list
   - For retry/investigation

## Data Extracted Per Property

### Contact Information (Most Important!)
- ✅ **Phone Number** (advertiser.phone)
- Advertiser Name
- Client ID
- Website URL
- Logo

### Property Details
- Property ID
- Title
- Type (Flat, House, etc.)
- Rooms (min/max)
- Bathrooms (min/max)
- Surface area (m²)
- Price range
- Available units with details

### Location
- Full address
- Country, Region, Province
- City, District
- ZIP code
- GPS coordinates (lat/lng)

### Features & Amenities
- Pool, Garden, Parking
- Air conditioning, Heating
- Kitchen appliances
- Security systems
- And more...

### Media
- All property images (URLs)
- Video links (YouTube, hosted)

### Energy Certificate
- Energy efficiency rating
- Environment impact rating
- Numeric values

### Description
- Full property description in Spanish

### Metadata
- Creation/modification dates
- Premium status
- Virtual tour availability
- Scrape timestamp

## Rate Limiting

The scraper implements intelligent rate limiting:
- **2 second minimum delay** between requests
- Prevents server overload
- Thread-safe request timing
- Each thread gets a new IP via proxy rotation

## Error Handling

- Failed properties are logged with error messages
- Individual file saving prevents total data loss
- Thread-safe counters for statistics
- Comprehensive error logging

## Example Output (CSV)

```csv
Property ID,Title,Phone,Advertiser,Location,Price,URL
20528373,Can Parellada,+34933634028,CASEX,Begues,Contact for price,https://...
20520326,Residencial Mar,+34912345678,Inmobiliaria XYZ,Cartagena,€450000,https://...
```

## Workflow

1. Load property URLs from `all_properties.json`
2. Create 30 concurrent threads
3. Each thread:
   - Waits for rate limit slot (2 sec minimum)
   - Gets new proxy IP
   - Scrapes property page
   - Extracts all data including phone
   - Saves individual JSON file
4. Merge all files into:
   - Complete JSON dataset
   - CSV with contact info
5. Log statistics and failures

## Performance

With 30 threads and 2-second rate limiting:
- Approximately 15 properties/second
- 900 properties/minute
- 1000 properties ≈ 70 seconds

Actual time may be longer due to network latency and server response times.

## Troubleshooting

**No data extracted:**
- Check if property URL is valid
- Verify proxy is working
- Check failed_properties.log for details

**Rate limit errors:**
- Increase DELAY_BETWEEN_REQUESTS
- Reduce MAX_THREADS

**Timeout errors:**
- Increase timeout in session.get()
- Check proxy status

## Next Steps

After running this scraper:
1. Check `property_contacts.csv` for all phone numbers
2. Review `all_property_details.json` for complete data
3. Retry failed properties if needed
4. Import CSV into your CRM or contact system
