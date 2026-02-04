import { chromium, Browser, BrowserContext, Page } from 'playwright';
import { ScraperLogger } from '@shared/logger.js';
import { normalizeProperty, extractListingsFromPage } from './parser.js';
import type { FinnConfig, SearchOptions, FinnProperty, TransactionType, CityInfo, PageListing } from './types.js';

const BASE_URL = 'https://www.finn.no';

const CITIES: Record<string, CityInfo> = {
  oslo: { code: 'OSLO', name: 'Oslo', county: 'Akershus og Oslo' },
  bergen: { code: 'HORDALAND', name: 'Bergen', county: 'Hordaland' },
  trondheim: { code: 'SOER_TROENDELAG', name: 'Trondheim', county: 'Sør-Trøndelag' },
  stavanger: { code: 'ROGALAND', name: 'Stavanger', county: 'Rogaland' },
  kristiansand: { code: 'VEST_AGDER', name: 'Kristiansand', county: 'Vest-Agder' },
  drammen: { code: 'BUSKERUD', name: 'Drammen', county: 'Buskerud' },
  fredrikstad: { code: 'OESTFOLD', name: 'Fredrikstad', county: 'Østfold' },
  aalesund: { code: 'MOERE_OG_ROMSDAL', name: 'Ålesund', county: 'Møre og Romsdal' },
  tonsberg: { code: 'VESTFOLD', name: 'Tønsberg', county: 'Vestfold' },
  sandefjord: { code: 'VESTFOLD', name: 'Sandefjord', county: 'Vestfold' },
  lillehammer: { code: 'OPPLAND', name: 'Lillehammer', county: 'Oppland' },
  hamar: { code: 'HEDMARK', name: 'Hamar', county: 'Hedmark' },
  steinkjer: { code: 'NORD_TROENDELAG', name: 'Steinkjer', county: 'Nord-Trøndelag' },
  bodo: { code: 'NORDLAND', name: 'Bodø', county: 'Nordland' },
  tromsoe: { code: 'TROMS', name: 'Tromsø', county: 'Troms' },
  alta: { code: 'FINNMARK', name: 'Alta', county: 'Finnmark' },
};

/**
 * Finn.no Scraper
 *
 * Scrapes property listings from Finn.no, Norway's largest real estate portal.
 *
 * Features:
 * - 15+ fields per property
 * - Multiple property types
 * - Sale and rental listings
 * - Pagination support (1000+ properties possible)
 * - County/Regional search
 */
export class FinnScraper {
  private config: FinnConfig;
  private browser: Browser | null = null;
  private context: BrowserContext | null = null;
  private page: Page | null = null;
  private logger: ScraperLogger;

  constructor(config: FinnConfig = {}) {
    this.config = {
      headless: true,
      timeout: 60000,
      delayMs: 2000,
      ...config,
    };
    this.logger = new ScraperLogger('finn-scraper');
    this.logger.initializeScraper('finn.no', { headless: this.config.headless });
  }

  /**
   * Initialize browser and context
   */
  async init(): Promise<void> {
    this.logger.info('Initializing Finn scraper');
    try {
      this.browser = await chromium.launch({
        headless: this.config.headless !== false,
        args: [
          '--disable-blink-features=AutomationControlled',
          '--no-sandbox',
          '--disable-setuid-sandbox',
        ],
      });

      this.context = await this.browser.newContext({
        userAgent:
          'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        viewport: { width: 1920, height: 1080 },
        locale: 'nb-NO',
      });

      this.page = await this.context.newPage();

      // Mask webdriver
      await this.page.addInitScript(() => {
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
        Object.defineProperty(navigator, 'languages', { get: () => ['nb-NO', 'nb', 'en-US'] });
        (window as any).chrome = { runtime: {} };
      });

      this.logger.info('Browser initialized successfully');
    } catch (error) {
      this.logger.error('Failed to initialize browser', error);
      throw error;
    }
  }

  /**
   * Close browser
   */
  async close(): Promise<void> {
    try {
      if (this.page) await this.page.close();
      if (this.context) await this.context.close();
      if (this.browser) await this.browser.close();
      this.logger.info('Browser closed');
    } catch (error) {
      this.logger.error('Error closing browser', error);
    }
  }

  /**
   * Build search URL
   */
  private buildSearchUrl(city: string, page: number, transactionType: TransactionType): string {
    const typeUrl = transactionType === 'rent' ? 'leilighet/utleie' : 'bolig/sal';
    const cityCode = typeof city === 'string' ? CITIES[city]?.code || city : city;
    const pageParam = page > 1 ? `&page=${page}` : '';
    return `${BASE_URL}/${typeUrl}/?county=${cityCode}${pageParam}`;
  }

  /**
   * Delay execution
   */
  private async delay(ms: number): Promise<void> {
    this.logger.logRateLimit(ms);
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  /**
   * Search for properties
   */
  private async searchInternal(
    transactionType: TransactionType,
    options: SearchOptions,
  ): Promise<FinnProperty[]> {
    const { city = 'oslo', maxPages = 1, delayMs = this.config.delayMs } = options;

    if (!this.browser) {
      await this.init();
    }

    try {
      const cityInfo = typeof city === 'string' ? CITIES[city] : (city as unknown as CityInfo);
      if (!cityInfo) {
        throw new Error(`Unknown city: ${city}`);
      }

      this.logger.info(`Starting ${transactionType} search for ${cityInfo.name}`, { maxPages });

      const allListings: FinnProperty[] = [];
      let pageNum = 1;

      while (pageNum <= maxPages) {
        const url = this.buildSearchUrl(city as string, pageNum, transactionType);
        this.logger.logPageFetch(url, pageNum);

        try {
          const response = await this.page!.goto(url, {
            waitUntil: 'domcontentloaded',
            timeout: this.config.timeout,
          });

          if (!response?.ok()) {
            this.logger.warn(`Failed to load page: ${response?.status()}`);
            break;
          }

          // Wait for content to load
          await this.page!.waitForTimeout(2000);

          // Extract listings
          const extracted = await this.page!.evaluate(extractListingsFromPage);
          const normalized = extracted
            .map((listing: PageListing) => normalizeProperty(listing, transactionType))
            .filter((p): p is FinnProperty => p !== null);

          if (normalized.length === 0) {
            this.logger.info(`No listings found on page ${pageNum}`);
            break;
          }

          allListings.push(...normalized);
          this.logger.logProgress(pageNum, maxPages, `Extracted ${normalized.length} listings`);

          // Check for next page
          const hasNextPage = await this.page!.evaluate(() => {
            return !!document.querySelector('a[rel="next"]');
          });

          if (!hasNextPage) {
            this.logger.info('No more pages available');
            break;
          }

          pageNum++;

          if (pageNum <= maxPages && delayMs) {
            await this.delay(delayMs + Math.random() * 1000);
          }
        } catch (error) {
          this.logger.error(`Error on page ${pageNum}`, error);
          break;
        }
      }

      this.logger.completeScraper({
        city: cityInfo.name,
        totalListings: allListings.length,
        pagesScraped: pageNum,
      });

      return allListings;
    } catch (error) {
      this.logger.error('Search error', error);
      throw error;
    }
  }

  /**
   * Search for buy properties
   */
  async searchBuy(options: SearchOptions = {}): Promise<FinnProperty[]> {
    return this.searchInternal('sale', options);
  }

  /**
   * Search for rental properties
   */
  async searchRent(options: SearchOptions = {}): Promise<FinnProperty[]> {
    return this.searchInternal('rent', options);
  }
}
