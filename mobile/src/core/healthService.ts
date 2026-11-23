import { getApiBaseUrl } from './networkConfig';

export interface HealthStatus {
  status: string;
}

export const healthService = {
  getHealth: async (): Promise<HealthStatus> => {
    const baseUrl = getApiBaseUrl();
    const rootBaseUrl = baseUrl.replace(/\/api\/v1\/?$/, '');
    const url = `${rootBaseUrl}/health`;

    try {
      const response = await fetch(url, {
        method: 'GET',
        headers: {
          Accept: 'application/json',
        },
      });

      if (!response.ok) {
        throw new Error(`HTTP Error ${response.status}`);
      }

      return (await response.json()) as HealthStatus;
    } catch (error: any) {
      throw new Error(error.message || 'Failed to connect to health API');
    }
  },
};
