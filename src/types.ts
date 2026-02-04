/**
 * Finn.no Scraper Type Definitions
 */

export type TransactionType = 'sale' | 'rent';

/**
 * Finn Scraper Configuration
 */
export interface FinnConfig {
  headless?: boolean;
  timeout?: number;
  delayMs?: number;
  redisUrl?: string;
}

/**
 * City Configuration
 */
export interface CityInfo {
  code: string;
  name: string;
  county?: string;
}

/**
 * Finn Property Listing
 */
export interface FinnProperty {
  id: string;
  source: string;
  url: string;
  title: string;
  price: number | null;
  currency: string;
  priceUnit: 'total' | 'per_month';
  propertyType: string;
  transactionType: TransactionType;
  status?: string;
  location: {
    address?: string;
    city: string;
    county?: string;
    country: string;
    postalCode?: string;
    latitude?: number;
    longitude?: number;
  };
  details: {
    sqm?: number;
    rooms?: number;
    bedrooms?: number;
    bathrooms?: number;
    yearBuilt?: number;
    buildingType?: string;
  };
  features: string[];
  images: string[];
  description?: string;
  agent?: {
    name?: string;
    phone?: string;
    email?: string;
  };
  scrapedAt: string;
}

/**
 * Search Options
 */
export interface SearchOptions {
  city?: string;
  maxPages?: number;
  delayMs?: number;
  priceMin?: number;
  priceMax?: number;
  areaMin?: number;
  areaMax?: number;
  roomsMin?: number;
  roomsMax?: number;
}

/**
 * Page Listing (raw from page)
 */
export interface PageListing {
  id: string;
  title?: string;
  price?: string | number;
  address?: string;
  city?: string;
  county?: string;
  sqm?: string | number;
  rooms?: string | number;
  bedrooms?: string | number;
  link?: string;
  image?: string;
  [key: string]: unknown;
}
