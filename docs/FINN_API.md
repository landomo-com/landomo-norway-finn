# FINN.no Real Estate API Documentation

## Overview

FINN.no is Norway's largest online marketplace, similar to Craigslist but dominant across multiple categories including real estate. It's owned by Schibsted, one of the largest media groups in Scandinavia.

## Market Position

- **Market Leader**: FINN.no is the most important channel for buying and selling property in Norway
- **Schibsted Ownership**: Part of Schibsted's classified portfolio (also owns Blocket in Sweden, Leboncoin in France)
- **Market Share**: Accounts for approximately 80% of Schibsted's NOK 216 million real estate revenue (Q1 2023)
- **Mobile Apps**: Available on iOS and Android with full functionality

## Current Listing Counts (January 2026)

| Category | National Total | Oslo | Bergen |
|----------|----------------|------|--------|
| Rentals (Til leie) | ~10,564 | ~2,526 | ~1,356 |
| For Sale (Bolig til salgs) | ~35,059 | ~3,577 | ~6,466 |
| New Construction | ~18,992 | - | - |

## API Architecture

### Official API (api.finn.no)
FINN.no has an official REST API but it requires:
- Business relationship with FINN
- API key obtained through business contact
- `orgId` parameter for all searches (FINN-specific advertiser ID)

**Endpoint**: `https://cache.api.finn.no/iad/search/`
**Format**: Atom/XML with OpenSearch extensions
**Authentication**: Custom header `x-FINN-apikey: <API-key>`

The official API is available to:
- Real estate agents
- Car dealers
- Business partners
- Advertisers

### Web Scraping Approach (This Scraper)
Since the official API requires business authentication, this scraper uses web scraping:

1. **Data Embedding**: FINN.no embeds listing data as JSON within HTML
2. **Format**: `{"type":"realestate","id":"...","heading":"...","location":"...",...}`
3. **Pagination**: Via `?page=N` URL parameter
4. **Results per page**: ~51 listings

## URL Structure

### Search URLs
```
https://www.finn.no/realestate/{type}/search.html?{params}
```

Types:
- `lettings` - Rental properties
- `homes` - Properties for sale
- `newbuildings` - New construction projects
- `leisuresale` - Vacation homes (Fritidsbolig)
- `plots` - Building plots
- `commercial` - Commercial real estate

### Listing Detail URLs
```
https://www.finn.no/realestate/{type}/ad.html?finnkode={id}
```

## Query Parameters

| Parameter | Description | Example |
|-----------|-------------|---------|
| `location` | FINN location code | `0.20061` (Oslo) |
| `price_from` | Minimum price | `5000` |
| `price_to` | Maximum price | `15000` |
| `area_from` | Minimum area (sqm) | `30` |
| `area_to` | Maximum area (sqm) | `100` |
| `no_of_bedrooms_from` | Minimum bedrooms | `2` |
| `no_of_bedrooms_to` | Maximum bedrooms | `4` |
| `property_type` | Property type code | `1` (apartment) |
| `sort` | Sort option | `PUBLISHED_DESC` |
| `page` | Page number | `2` |
| `q` | Keyword search | `balkong` |

## Location Codes

Major cities:
| City | Code |
|------|------|
| Oslo | `0.20061` |
| Bergen | `0.20003` |
| Trondheim | `0.20016` |
| Stavanger | `0.20012` |
| Kristiansand | `0.20011` |
| Tromso | `0.20019` |
| Drammen | `0.20006` |

Counties (Fylker):
| County | Code |
|--------|------|
| Viken | `0.20030` |
| Vestland | `0.20046` |
| Rogaland | `0.20011` |
| Trondelag | `0.20050` |

## Listing Data Structure

```json
{
  "type": "realestate",
  "id": "448603189",
  "main_search_key": "SEARCH_ID_REALESTATE_LETTINGS",
  "heading": "Moderne 2-roms leilighet i sentrum",
  "location": "Karl Johans gate 1, Oslo",
  "image": {
    "url": "https://images.finncdn.no/dynamic/default/item/448603189/...",
    "path": "item/448603189/...",
    "height": 1067,
    "width": 1600,
    "aspect_ratio": 1.499
  },
  "flags": ["verified", "private"]
}
```

## Usage Examples

### Python Client

```python
from finn_api import FinnClient, SearchType

client = FinnClient()

# Search rentals in Oslo
results = client.search_lettings(location="0.20061")
print(f"Found {results.total_count} rentals")

# Search homes with price filter
results = client.search_homes(
    location="0.20003",  # Bergen
    price_from=2000000,
    price_to=5000000
)

# Iterate through all pages
for listing in client.search_all_pages(
    SearchType.LETTINGS,
    location="0.20061",
    max_pages=5
):
    print(f"{listing.id}: {listing.heading}")

# Get listing details
details = client.get_listing_details("448603189")
```

### Command Line

```bash
# Search rentals in Oslo
python finn_api.py --type lettings --location oslo

# Search homes with price filter
python finn_api.py --type homes --location bergen --price-from 2000000 --price-to 5000000

# Get listing details
python finn_api.py --details 448603189

# Save results to JSON
python finn_api.py --type lettings --location oslo --output oslo_rentals.json
```

## Rate Limiting

- Default delay: 1 second between requests
- Recommended: Keep delay at 1+ seconds for production use
- FINN.no does not aggressively block scrapers but may rate limit heavy usage

## Anti-Bot Protection

FINN.no uses:
- Standard rate limiting
- CloudFront CDN
- Cookie/session tracking

The scraper works without issues using:
- Standard browser User-Agent
- Minimal headers (avoid Accept-Encoding)
- Reasonable delays between requests

## Related Platforms in Norway

| Platform | Focus | URL |
|----------|-------|-----|
| Hybel.no | Student/shared housing | hybel.no |
| OBOS | Cooperative housing | obos.no |
| Krogsveen | Real estate agency | krogsveen.no |
| Boligportalen | Rentals | boligportalen.no |

## Sources

- [FINN.no Real Estate](https://www.finn.no/realestate/)
- [FINN API Documentation](https://www.finn.no/api/doc/search)
- [Similarweb - Top Real Estate Sites Norway](https://www.similarweb.com/top-websites/norway/business-and-consumer-services/real-estate/)
