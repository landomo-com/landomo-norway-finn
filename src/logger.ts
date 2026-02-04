import pino from 'pino';

/**
 * Simple logger wrapper for Finn scraper
 */
export class ScraperLogger {
  private logger: pino.Logger;
  private context: string;

  constructor(context: string) {
    this.context = context;
    this.logger = pino({
      transport: {
        target: 'pino-pretty',
        options: {
          colorize: true,
          translateTime: 'HH:MM:ss',
          ignore: 'pid,hostname',
        },
      },
      level: process.env.LOG_LEVEL || 'info',
    });
  }

  info(message: string, meta?: any): void {
    this.logger.info({ context: this.context, ...meta }, message);
  }

  warn(message: string, meta?: any): void {
    this.logger.warn({ context: this.context, ...meta }, message);
  }

  error(message: string, error?: any): void {
    this.logger.error({ context: this.context, error }, message);
  }

  debug(message: string, meta?: any): void {
    this.logger.debug({ context: this.context, ...meta }, message);
  }

  initializeScraper(portal: string, config: any): void {
    this.info(`Initializing scraper for ${portal}`, config);
  }

  logPageFetch(url: string, page: number): void {
    this.info(`Fetching page ${page}`, { url });
  }

  logProgress(current: number, total: number, message?: string): void {
    this.info(`Progress: ${current}/${total}`, { message });
  }

  logRateLimit(delayMs: number): void {
    this.debug(`Rate limiting: ${delayMs}ms delay`);
  }

  completeScraper(stats: any): void {
    this.info('Scraping complete', stats);
  }
}
