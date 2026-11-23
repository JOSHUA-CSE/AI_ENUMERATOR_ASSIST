import { getApiBaseUrl, setBaseUrl as setConfigBaseUrl } from './networkConfig';
import { secureStore } from './secureStore';

export let API_BASE_URL = getApiBaseUrl();

export const setBaseUrl = (url: string) => {
  API_BASE_URL = url;
  setConfigBaseUrl(url);
};

export function extractErrorMessage(detailOrError: any): string {
  if (!detailOrError) return 'An unexpected error occurred. Please try again.';

  if (typeof detailOrError === 'string') {
    const trimmed = detailOrError.trim();
    if (!trimmed || trimmed === '[object Object]' || trimmed === '{}') {
      return 'An unexpected error occurred. Please try again.';
    }
    try {
      const parsed = JSON.parse(trimmed);
      if (parsed && typeof parsed === 'object') {
        return extractErrorMessage(parsed);
      }
    } catch {
      // Plain string
    }
    return trimmed;
  }

  // Handle Axios / Network response structures
  if (typeof detailOrError === 'object' && detailOrError.response?.data) {
    return extractErrorMessage(detailOrError.response.data);
  }

  // If it's a FastAPI validation error list: [{ loc: [...], msg: "...", type: "..." }]
  if (Array.isArray(detailOrError)) {
    const messages = detailOrError
      .map((item) => {
        if (!item) return '';
        if (typeof item === 'string') return item;
        if (typeof item === 'object') {
          const field = Array.isArray(item.loc) ? item.loc[item.loc.length - 1] : '';
          const msg = item.msg || item.message || '';
          if (field && msg) return `${field}: ${msg}`;
          if (msg) return msg;
        }
        return '';
      })
      .filter(Boolean);
    if (messages.length > 0) return messages.join(' • ');
    return 'Validation failed. Please verify the input.';
  }

  // If it's an Error instance
  if (detailOrError instanceof Error) {
    if (detailOrError.message && detailOrError.message !== '[object Object]' && detailOrError.message.trim() !== '{}') {
      return extractErrorMessage(detailOrError.message);
    }
  }

  // If it's an object with detail, message, or error property
  if (typeof detailOrError === 'object') {
    if (detailOrError.detail) {
      return extractErrorMessage(detailOrError.detail);
    }
    if (detailOrError.message && typeof detailOrError.message === 'string' && detailOrError.message !== '[object Object]') {
      return detailOrError.message;
    }
    if (detailOrError.error && typeof detailOrError.error === 'string') {
      return detailOrError.error;
    }
    if (detailOrError.statusText && typeof detailOrError.statusText === 'string') {
      return `HTTP Error: ${detailOrError.statusText}`;
    }
    try {
      const str = JSON.stringify(detailOrError);
      if (str && str !== '{}' && str !== '[]') {
        return str;
      }
    } catch {
      // Fallback
    }
    return 'An unexpected error occurred. Please try again.';
  }

  const result = String(detailOrError);
  return result === '[object Object]' || result === '{}' ? 'An unexpected error occurred. Please try again.' : result;
}

export class ApiError extends Error {
  status?: number;
  data?: any;

  constructor(messageOrDetail: any, status?: number, data?: any) {
    const cleanMessage = extractErrorMessage(messageOrDetail);
    super(cleanMessage);
    this.name = 'ApiError';
    this.status = status;
    this.data = data;
  }
}

interface RequestOptions {
  headers?: Record<string, string>;
  timeoutMs?: number;
}

const defaultTimeoutMs = 10000;

type UnauthorizedCallback = () => void;
let unauthorizedCallback: UnauthorizedCallback | null = null;
let activeAuthToken: string | null = null;

export const setUnauthorizedCallback = (callback: UnauthorizedCallback) => {
  unauthorizedCallback = callback;
};

export const setAuthToken = (token: string | null) => {
  activeAuthToken = token;
};

export const getAuthToken = () => activeAuthToken;

async function request<T>(
  method: 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE',
  path: string,
  body?: any,
  options: RequestOptions = {}
): Promise<T> {
  const baseUrl = getApiBaseUrl();
  const url = `${baseUrl}${path}`;
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), options.timeoutMs ?? defaultTimeoutMs);

  const token = activeAuthToken || (await secureStore.getToken());

  const headers = {
    'Content-Type': 'application/json',
    Accept: 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...options.headers,
  };

  try {
    const response = await fetch(url, {
      method,
      headers,
      body: body ? JSON.stringify(body) : undefined,
      signal: controller.signal as any,
    });

    clearTimeout(timeoutId);

    const text = await response.text();
    let data: any;
    try {
      data = text ? JSON.parse(text) : null;
    } catch {
      data = text;
    }

    if (!response.ok) {
      if (response.status === 401) {
        if (unauthorizedCallback) {
          unauthorizedCallback();
        }
      }
      throw new ApiError(
        data?.detail || `HTTP Error ${response.status}: ${response.statusText}`,
        response.status,
        data
      );
    }

    return data as T;
  } catch (error: any) {
    clearTimeout(timeoutId);

    if (error.name === 'AbortError') {
      throw new ApiError('Request timed out', 408);
    }
    if (error instanceof ApiError) {
      throw error;
    }
    const rawMsg = error?.message || 'Network error occurred';
    if (
      rawMsg.includes('Network request failed') ||
      rawMsg.includes('Failed to fetch') ||
      rawMsg.includes('fetch failed')
    ) {
      const activeUrl = getApiBaseUrl();
      throw new ApiError(
        `Unable to reach backend API at ${activeUrl}. Please ensure:\n• Phone and laptop are connected to the same Wi-Fi\n• FastAPI is running on port 8000 (0.0.0.0:8000)\n• Windows firewall allows inbound connections on port 8000`
      );
    }
    throw new ApiError(rawMsg);
  }
}

export const apiClient = {
  get: <T>(path: string, options?: RequestOptions) => request<T>('GET', path, undefined, options),
  post: <T>(path: string, body: any, options?: RequestOptions) => request<T>('POST', path, body, options),
  patch: <T>(path: string, body?: any, options?: RequestOptions) => request<T>('PATCH', path, body, options),
  put: <T>(path: string, body?: any, options?: RequestOptions) => request<T>('PUT', path, body, options),
  delete: <T>(path: string, options?: RequestOptions) => request<T>('DELETE', path, undefined, options),
};
