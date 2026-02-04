# Landomo Scraper: norway - finn

Scraper for **finn_NAME** in **norway_NAME**.

## Overview

This scraper extracts real estate listings from finn_NAME and sends them to the Landomo Core Service for standardization and storage.

**Portal URL**: https://finn_URL
**Country**: norway_NAME
**Status**: Development

## Quick Start

1. **Install dependencies**:
   ```bash
   npm install
   ```

2. **Configure environment**:
   ```bash
   cp .env.example .env
   # Edit .env and add your LANDOMO_API_KEY
   ```

3. **Run scraper**:
   ```bash
   npm start
   ```

4. **Development mode** (auto-reload):
   ```bash
   npm run dev
   ```

## Configuration

See `.env.example` for all configuration options.

Required:
- `LANDOMO_API_KEY` - API key for Landomo Core Service

Optional:
- `DEBUG=true` - Enable debug logging
- `REQUEST_DELAY_MS` - Delay between requests (default: 1000ms)
- Proxy configuration for bypassing geo-restrictions

## Architecture

This scraper follows the standard Landomo scraper pattern:

```
Portal → Scraper → Transformer → Core Service → Core DB
```

### Files

- `src/scraper.ts` - Main scraping logic
- `src/transformer.ts` - Portal data → StandardProperty conversion
- `src/types.ts` - TypeScript type definitions
- `src/config.ts` - Configuration management

## Development

### Testing

```bash
# Run tests
npm test

# Run tests in watch mode
npm run test:watch
```

### Type Checking

```bash
npm run type-check
```

### Linting

```bash
npm run lint
```

## Portal-Specific Notes

TODO: Add any portal-specific information:
- Authentication requirements
- Rate limiting details
- Known issues or quirks
- Bot detection handling

## Deployment

This scraper is deployed via GitHub Actions on every push to `main`.

See `.github/workflows/deploy.yml` for deployment configuration.

## Contributing

See the main [Landomo Registry](https://github.com/landomo-com/landomo-registry) for contribution guidelines.

## License

UNLICENSED - Internal use only
