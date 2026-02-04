# Landomo Scraper: Norway - Finn.no

Scraper for **Finn.no** in **Norway**.

## Overview

This scraper extracts real estate listings from Finn.no, Norway's largest online marketplace and property portal. Finn.no is owned by Schibsted and accounts for ~80% of the Norwegian real estate market.

**Portal URL**: https://www.finn.no
**Country**: Norway
**Status**: Production Ready
**Market Coverage**: ~45,000+ listings (35,000 for sale + 10,000 rentals)

## Features

- Browser automation (Playwright) for web scraping
- API client for official Finn.no API (requires authentication)
- Support for both sale and rental properties
- 15+ fields per property
- Pagination support (1000+ properties)
- County/Regional search across 16 major cities

## Quick Start

1. **Install dependencies**:
   ```bash
   npm install
   ```

2. **Run scraper** (web scraping mode):
   ```bash
   npm run build
   npm start -- --city oslo --max-pages 2
   ```

3. **Development mode**:
   ```bash
   npm run dev -- --city bergen --rent
   ```

## Usage

### Command Line Options

```bash
# Scrape properties for sale in Oslo (1 page)
npm start -- --city oslo --max-pages 1

# Scrape rental properties in Bergen (5 pages)
npm start -- --city bergen --rent --max-pages 5

# Available cities:
# oslo, bergen, trondheim, stavanger, kristiansand, drammen,
# fredrikstad, aalesund, tonsberg, sandefjord, lillehammer,
# hamar, steinkjer, bodo, tromsoe, alta
```

### Programmatic Usage

```typescript
import { FinnScraper } from './src/scraper.js';

const scraper = new FinnScraper({ headless: true });

await scraper.init();

// Search for properties
const properties = await scraper.searchBuy({
  city: 'oslo',
  maxPages: 5,
});

console.log(`Found ${properties.length} properties`);

await scraper.close();
```

## Architecture

This scraper uses **browser automation** with Playwright to extract listing data from Finn.no's search results pages.

### Data Flow

```
Finn.no Search Page → Playwright → Parser → Normalized Property → Output
```

### Files

- `src/scraper.ts` - Main Playwright-based scraper
- `src/api-scraper.ts` - API-based scraper (requires API key)
- `src/parser.ts` - HTML parsing and normalization
- `src/types.ts` - TypeScript type definitions
- `src/logger.ts` - Logging utilities
- `src/api-client.ts` - Base API client

## Portal-Specific Details

### Finn.no Market

- **Market Leader**: ~80% market share in Norway
- **Listing Volume**: 35,000+ for sale, 10,000+ rentals
- **Coverage**: All major cities and counties
- **Language**: Norwegian (Bokmål)

### Scraping Approach

**Web Scraping Mode** (Default):
- Uses Playwright for browser automation
- Extracts data from search result pages
- Handles pagination automatically
- No authentication required
- Rate limiting: 2-3 seconds between pages

**API Mode** (Optional):
- Requires business relationship with Finn.no
- Requires API key and `orgId` parameter
- Faster and more reliable
- See `src/api-scraper.ts`

### Anti-Bot Protection

Finn.no uses:
- Standard rate limiting
- CloudFront CDN
- Cookie/session tracking

The scraper handles this by:
- Using realistic browser fingerprints
- Random delays between requests (2-3 seconds)
- Norwegian locale and User-Agent
- Masking webdriver flags

### Data Structure

```typescript
{
  id: string;
  source: "finn-norway";
  url: string;
  title: string;
  price: number | null;
  currency: "NOK";
  priceUnit: "total" | "per_month";
  propertyType: "apartment" | "house" | "townhouse" | "studio";
  transactionType: "sale" | "rent";
  location: {
    address: string;
    city: string;
    county: string;
    country: "Norway";
  };
  details: {
    sqm: number;
    rooms: number;
    bedrooms: number;
  };
  features: string[];
  images: string[];
  scrapedAt: string;
}
```

## Development

### Type Checking

```bash
npm run lint
```

### Building

```bash
npm run build
```

### Cleaning

```bash
npm run clean
```

## Deployment

This scraper is deployed via GitHub Actions on every push to `main`.

See `.github/workflows/deploy.yml` for deployment configuration.

## Documentation

See `docs/FINN_API.md` for detailed API documentation and market research.

## Related Platforms

- **Hybel.no** - Student/shared housing
- **OBOS** - Cooperative housing
- **Krogsveen** - Real estate agency

## Contributing

See the main [Landomo Registry](https://github.com/landomo-com/landomo-registry) for contribution guidelines.

## License

UNLICENSED - Internal use only
