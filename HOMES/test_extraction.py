import re
import json

# Read the sample HTML
with open('house_pagination_first_page.html', 'r', encoding='utf-8') as f:
    html_content = f.read()

# Find the JSON data in window.__INITIAL_PROPS__
match = re.search(r'window\.__INITIAL_PROPS__\s*=\s*JSON\.parse\("(.+?)"\);', html_content, re.DOTALL)

if match:
    print("✓ Found window.__INITIAL_PROPS__")
    json_str = match.group(1)

    # Unescape the JSON string
    json_str = json_str.encode('utf-8').decode('unicode_escape')

    # Parse JSON
    data = json.loads(json_str)
    print(f"✓ JSON parsed successfully")

    # Navigate to the property listings
    if 'initialSearch' in data and 'result' in data['initialSearch']:
        result = data['initialSearch']['result']

        # Check for realEstates array
        if 'realEstates' in result:
            properties = result['realEstates']
            print(f"\n✓ Found {len(properties)} properties in realEstates")

            # Extract property links
            print("\n" + "="*80)
            print("PROPERTY LINKS:")
            print("="*80)

            for i, prop in enumerate(properties[:10], 1):  # Show first 10
                if 'detailUrl' in prop:
                    prop_id = prop.get('id', 'N/A')
                    location = prop.get('location', {})
                    if isinstance(location, dict):
                        zone = location.get('zone', 'N/A')
                    else:
                        zone = location if location else 'N/A'

                    price_info = prop.get('price', {})
                    if isinstance(price_info, dict):
                        price = price_info.get('amount', 'N/A')
                    elif isinstance(price_info, str):
                        price = price_info
                    else:
                        price = 'N/A'

                    detail_url = prop['detailUrl']
                    full_url = f"https://www.fotocasa.es{detail_url}"

                    print(f"\n{i}. ID: {prop_id}")
                    print(f"   Location: {zone}")
                    print(f"   Price: {price}")
                    print(f"   URL: {full_url}")

            print(f"\n... and {len(properties) - 10} more properties")
        else:
            print("✗ No 'realEstates' key found in result")
            print(f"Available keys: {list(result.keys())}")
    else:
        print("✗ Could not find initialSearch.result in data")
        print(f"Top level keys: {list(data.keys())}")
else:
    print("✗ Could not find window.__INITIAL_PROPS__")

    # Try to find what's there
    print("\nSearching for window.__INITIAL")
    matches = re.findall(r'window\.__INITIAL[A-Z_]+', html_content)
    print(f"Found: {set(matches)}")
