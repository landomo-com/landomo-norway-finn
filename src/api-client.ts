/**
 * Simple API client base class
 */
export interface ApiConfig {
  baseUrl: string;
  timeout?: number;
  requestsPerSecond?: number;
}

export class BaseApiClient {
  protected baseUrl: string;
  protected timeout: number;
  protected requestsPerSecond: number;
  protected lastRequestTime: number = 0;

  constructor(config: ApiConfig, private name: string) {
    this.baseUrl = config.baseUrl;
    this.timeout = config.timeout || 30000;
    this.requestsPerSecond = config.requestsPerSecond || 2;
  }

  protected async delay(ms: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  protected async rateLimit(): Promise<void> {
    const minDelay = 1000 / this.requestsPerSecond;
    const elapsed = Date.now() - this.lastRequestTime;

    if (elapsed < minDelay) {
      await this.delay(minDelay - elapsed);
    }

    this.lastRequestTime = Date.now();
  }

  protected async get<T>(path: string, params?: Record<string, unknown>): Promise<{ data: T; status: number }> {
    await this.rateLimit();

    const url = new URL(path, this.baseUrl);

    if (params) {
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== null) {
          url.searchParams.append(key, String(value));
        }
      });
    }

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), this.timeout);

    try {
      const response = await fetch(url.toString(), {
        method: 'GET',
        headers: {
          'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        },
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const data = await response.json() as T;
      return { data, status: response.status };
    } catch (error) {
      clearTimeout(timeoutId);
      throw error;
    }
  }
}
