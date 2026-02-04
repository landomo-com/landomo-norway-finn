import type { PageListing, FinnProperty, TransactionType } from './types.js';

const BASE_URL = 'https://www.finn.no';

/**
 * Parse price string to number (Norwegian format)
 */
function parsePrice(priceText: string | null): number | null {
  if (!priceText) return null;
  // Remove 'kr', spaces, and other non-numeric characters
  const cleaned = priceText.replace(/[^\d]/g, '');
  const num = parseInt(cleaned, 10);
  return isNaN(num) ? null : num;
}

/**
 * Detect if price is monthly (per måned) or total
 */
function determinePriceUnit(priceText: string): 'total' | 'per_month' {
  if (!priceText) return 'total';
  return priceText.toLowerCase().includes('per måned') || priceText.toLowerCase().includes('/måned')
    ? 'per_month'
    : 'total';
}

/**
 * Extract sqm from text
 */
function extractSqm(text: string | null): number | undefined {
  if (!text) return undefined;
  const match = text.match(/(\d+)\s*m[²2]/i);
  return match ? parseInt(match[1], 10) : undefined;
}

/**
 * Extract number from text
 */
function extractNumber(text: string | null): number | undefined {
  if (!text) return undefined;
  const match = text.match(/(\d+)/);
  return match ? parseInt(match[1], 10) : undefined;
}

/**
 * Detect property type from URL and title
 */
function detectPropertyType(url: string, title: string): string {
  const combined = (url + ' ' + title).toLowerCase();
  if (combined.includes('leilighet') || combined.includes('apartment')) return 'apartment';
  if (combined.includes('villa') || combined.includes('hus') || combined.includes('house')) return 'house';
  if (combined.includes('studio')) return 'studio';
  if (combined.includes('rom') || combined.includes('room')) return 'room';
  if (combined.includes('rekkehus') || combined.includes('townhouse')) return 'townhouse';
  if (combined.includes('tomt') || combined.includes('land')) return 'land';
  return 'property';
}

/**
 * Parse page listing to normalized property
 */
export function normalizeProperty(
  listing: PageListing,
  transactionType: TransactionType,
): FinnProperty | null {
  if (!listing.title && !listing.price) {
    return null;
  }

  const url = listing.link || '#';
  const price = parsePrice(typeof listing.price === 'string' ? listing.price : String(listing.price || ''));
  const priceUnit = determinePriceUnit(typeof listing.price === 'string' ? listing.price : String(listing.price || ''));
  const sqm = extractSqm(typeof listing.sqm === 'string' ? listing.sqm : String(listing.sqm || ''));
  const rooms = extractNumber(typeof listing.rooms === 'string' ? listing.rooms : String(listing.rooms || ''));
  const bedrooms = extractNumber(
    typeof listing.bedrooms === 'string' ? listing.bedrooms : String(listing.bedrooms || ''),
  );

  return {
    id: listing.id || `finn-${Date.now()}-${Math.random()}`,
    source: 'finn-norway',
    url: url.startsWith('http') ? url : `${BASE_URL}${url}`,
    title: listing.title || listing.address || 'Property',
    price,
    currency: 'NOK',
    priceUnit,
    propertyType: detectPropertyType(url, listing.title || ''),
    transactionType,
    status: 'available',
    location: {
      address: listing.address,
      city: listing.city || 'Norway',
      county: listing.county,
      country: 'Norway',
    },
    details: {
      sqm,
      rooms,
      bedrooms,
    },
    features: [],
    images: listing.image ? [listing.image] : [],
    scrapedAt: new Date().toISOString(),
  };
}

/**
 * Parse listings page HTML using Playwright's evaluate context
 */
export function extractListingsFromPage(): PageListing[] {
  const items: PageListing[] = [];

  // Multiple selectors for different page layouts
  const selectors = [
    '[data-testid="search-result-item"]',
    '[data-test-id="result"]',
    '[class*="search-result"]',
    '[class*="listing-card"]',
    '[class*="property-card"]',
    'article[class*="item"]',
    'li[data-id]',
  ];

  let elements: Element[] = [];

  for (const selector of selectors) {
    const found = document.querySelectorAll(selector);
    if (found.length > 0) {
      elements = Array.from(found);
      break;
    }
  }

  elements.forEach((card: Element, index: number) => {
    try {
      const priceEl = card.querySelector('[class*="price"], span[class*="pris"]');
      const addressEl = card.querySelector('[class*="address"], [class*="adresse"], h2, h3');
      const cityEl = card.querySelector('[class*="city"], [class*="by"]');
      const sizeEl = card.querySelector('[class*="size"], [class*="area"], [class*="m2"], [class*="m²"]');
      const roomsEl = card.querySelector('[class*="room"], [class*="rom"]');
      const linkEl = card.querySelector('a[href*="/bolig/"]') || card.querySelector('a[href]');
      const imgEl = card.querySelector('img');

      const listing: PageListing = {
        id: (card as HTMLElement).getAttribute('data-id') || `listing-${index}`,
        title: addressEl?.textContent?.trim(),
        price: priceEl?.textContent?.trim(),
        address: addressEl?.textContent?.trim(),
        city: cityEl?.textContent?.trim(),
        sqm: sizeEl?.textContent?.trim(),
        rooms: roomsEl?.textContent?.trim(),
        link: linkEl?.getAttribute('href') || undefined,
        image: (imgEl as HTMLImageElement)?.src || (imgEl as HTMLImageElement)?.getAttribute('data-src') || undefined,
      };

      if (listing.title || listing.price) {
        items.push(listing);
      }
    } catch (e) {
      // Skip malformed items
    }
  });

  return items;
}
