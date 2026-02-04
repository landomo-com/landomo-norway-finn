import { FinnScraper } from './scraper.js';
import { ScraperLogger } from './logger.js';
import type { SearchOptions } from './types.js';

const logger = new ScraperLogger('finn-main');

function parseArgs(): {
  city?: string;
  maxPages?: number;
  rent?: boolean;
} {
  const args = process.argv.slice(2);
  const result: {
    city?: string;
    maxPages?: number;
    rent?: boolean;
  } = {};

  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--city' && args[i + 1]) {
      result.city = args[i + 1];
      i++;
    } else if (args[i] === '--max-pages' && args[i + 1]) {
      result.maxPages = parseInt(args[i + 1], 10);
      i++;
    } else if (args[i] === '--rent') {
      result.rent = true;
    }
  }

  return result;
}

async function main() {
  const args = parseArgs();

  const config: SearchOptions = {
    city: args.city || 'oslo',
    maxPages: args.maxPages || 1,
  };

  logger.info('Finn.no TypeScript Scraper');
  logger.info('==========================');
  logger.info(`City: ${config.city}`);
  logger.info(`Max Pages: ${config.maxPages}`);
  logger.info(`Listing Type: ${args.rent ? 'Rental' : 'For Sale'}`);
  logger.info('');

  const scraper = new FinnScraper({ headless: true });

  try {
    await scraper.init();
    const properties = args.rent ? await scraper.searchRent(config) : await scraper.searchBuy(config);

    if (properties.length > 0) {
      logger.info('\n=== Sample Properties ===');
      const samples = properties.slice(0, 3);
      for (const p of samples) {
        logger.info(`\n[${p.transactionType.toUpperCase()}] ${p.title}`);
        logger.info(          `  Price: ${p.price ? p.price.toLocaleString('nb-NO') + ' NOK' : 'N/A'}${p.priceUnit === 'per_month' ? '/month' : ''}`,        );
        logger.info(`  Type: ${p.propertyType}`);
        logger.info(`  Location: ${p.location.address || p.location.city}`);
        const detailParts = [
          p.details.sqm ? `${p.details.sqm} m²` : null,
          p.details.rooms ? `${p.details.rooms} rooms` : null,
          p.details.bedrooms ? `${p.details.bedrooms} bedrooms` : null,
        ]
          .filter(Boolean)
          .join(', ');
        logger.info(`  Details: ${detailParts || 'N/A'}`);
        logger.info(`  URL: ${p.url}`);
      }
    }

    logger.info(`\nScraping complete: ${properties.length} properties`);
  } catch (error) {
    logger.error('Scraper error:', error);
    process.exit(1);
  } finally {
    await scraper.close();
  }
}

main();
