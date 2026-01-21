# Quick Test Commands

## ✅ BUG FIXED!
**Issue**: `get_tracking_phone() takes 1 positional argument but 2 were given` - **RESOLVED**

The function now properly accepts both `promotion_id` and `property_url` parameters and uses POST request.

---

## Test NEW_CONSTRUCTIONS Scraper (with tracking phone API):
```powershell
cd G:\FOTOCASA\NEW_CONSTRUCTIONS
py -3.11 safe_property_scraper.py
```

**What to look for in the log:**
- ✅ `Found promotion ID: de195780-0b14-4862-9921-2a46b3b27f6b, fetching tracking phone...`
- ✅ `Got tracking phone for promotion {id}: +34518880004`
- ✅ `Final phone for property 20643452: +34518880004`

## Test HOMES Scraper (with Spain proxy):
```powershell
cd G:\FOTOCASA\HOMES
py -3.11 house_scraper.py
```

**What to look for in the log:**
- ✅ `Scraping page 1: https://www.fotocasa.es/es/comprar/viviendas/espana/todas-las-zonas/l`
- ✅ `Extracted {N} properties from page`
- ✅ No 405 errors (Spain proxy should prevent this)

## Check Progress:
```powershell
# Check NEW_CONSTRUCTIONS progress
cat G:\FOTOCASA\NEW_CONSTRUCTIONS\safe_property_scraper.log | Select-String "SUCCESS"

# Check HOMES progress
cat G:\FOTOCASA\HOMES\scraper.log | tail -50

# Check HOMES progress JSON
cat G:\FOTOCASA\HOMES\progress.json
```

## Check Output Files:
```powershell
# NEW_CONSTRUCTIONS output
ls G:\FOTOCASA\NEW_CONSTRUCTIONS\property_details\

# HOMES output
ls G:\FOTOCASA\HOMES\pages\

# Check final merged file
cat G:\FOTOCASA\HOMES\all_properties.json | ConvertFrom-Json | Select -ExpandProperty total_properties
```

## View Sample Property Data:
```powershell
# View a NEW_CONSTRUCTIONS property
cat G:\FOTOCASA\NEW_CONSTRUCTIONS\property_details\property_20643452.json | ConvertFrom-Json

# View a HOMES page
cat G:\FOTOCASA\HOMES\pages\page_00001.json | ConvertFrom-Json
```
