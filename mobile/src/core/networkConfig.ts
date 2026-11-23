import Constants from 'expo-constants';
import { Platform } from 'react-native';

export const DEFAULT_API_PORT = 8000;
export const DEFAULT_API_PATH = '/api/v1';

export interface ResolveOptions {
  envUrl?: string;
  hostUri?: string | null;
  platformOS?: string;
  webHostname?: string;
}

/**
 * Known tunnel domain patterns created by tools like Expo Tunnel or ngrok.
 * These domains route Metro bundler traffic over public web tunnels, but they
 * do NOT tunnel the backend FastAPI port (8000).
 */
const TUNNEL_PATTERNS = [
  'exp.direct',
  'ngrok.io',
  'ngrok-free.app',
  'ngrok.app',
  'loca.lt',
  'tunnel.expo.dev',
];

/**
 * Extracts a clean hostname or IPv4 address from a raw host URI or URL string.
 * Strips protocols (http://, exp://), ports (:8081), and trailing paths.
 *
 * Example: '172.17.4.177:8081' -> '172.17.4.177'
 * Example: 'http://10.132.120.48:19000/path' -> '10.132.120.48'
 */
export function extractHostname(rawHost?: string | null): string | null {
  if (!rawHost || typeof rawHost !== 'string') {
    return null;
  }

  let cleaned = rawHost.trim();
  if (!cleaned) {
    return null;
  }

  // Strip protocol prefix (e.g. http://, https://, exp://, exps://, ws://, wss://)
  cleaned = cleaned.replace(/^[a-zA-Z]+:\/\//, '');

  // Strip path and query parameters
  cleaned = cleaned.split('/')[0].split('?')[0];

  // Strip port (e.g. :8081)
  if (cleaned.includes(':')) {
    cleaned = cleaned.split(':')[0];
  }

  cleaned = cleaned.trim();
  return cleaned || null;
}

/**
 * Determines whether a hostname belongs to a public tunnel service rather
 * than a local area network (LAN) address.
 */
export function isTunnelHost(hostname?: string | null): boolean {
  if (!hostname || typeof hostname !== 'string') {
    return false;
  }
  const lower = hostname.toLowerCase();
  return TUNNEL_PATTERNS.some((pattern) => lower.includes(pattern));
}

/**
 * Retrieves the Expo development server host URI from available runtime metadata.
 */
export function getExpoHostUri(): string | null {
  try {
    const hostUri =
      Constants.expoConfig?.hostUri ||
      (Constants as any).manifest?.debuggerHost ||
      (Constants as any).manifest2?.extra?.expoGo?.debuggerHost ||
      (Constants as any).manifest?.hostUri;

    return typeof hostUri === 'string' && hostUri.trim() ? hostUri.trim() : null;
  } catch {
    return null;
  }
}

/**
 * Dynamically resolves the API base URL with the following priority:
 * 1. Explicit EXPO_PUBLIC_API_URL environment variable override.
 * 2. Web browser dynamic origin host (when running in web mode).
 * 3. Dynamic Expo development server host derived from hostUri (e.g. 172.17.4.177:8081 -> http://172.17.4.177:8000/api/v1).
 * 4. Fallback development host with descriptive troubleshooting guidance.
 */
export function resolveApiBaseUrl(options?: ResolveOptions): string {
  // 1. Explicit environment variable override
  const envUrl = options?.envUrl ?? process.env.EXPO_PUBLIC_API_URL;
  if (envUrl && typeof envUrl === 'string' && envUrl.trim()) {
    const trimmed = envUrl.trim().replace(/\/+$/, '');
    if (!trimmed.includes('brave-paths-double.loca.lt')) {
      return trimmed;
    }
  }

  const currentPlatform = options?.platformOS ?? Platform.OS;

  // 2. Web browser dynamic detection
  if (currentPlatform === 'web') {
    const webHost =
      options?.webHostname ??
      (typeof window !== 'undefined' && window.location?.hostname
        ? window.location.hostname
        : 'localhost');

    if (webHost === 'localhost' || webHost === '127.0.0.1') {
      return `http://localhost:${DEFAULT_API_PORT}${DEFAULT_API_PATH}`;
    }
    return `http://${webHost}:${DEFAULT_API_PORT}${DEFAULT_API_PATH}`;
  }

  // 3. Expo runtime development server host detection
  const rawHost = options?.hostUri !== undefined ? options.hostUri : getExpoHostUri();
  const hostname = extractHostname(rawHost);

  if (hostname) {
    if (isTunnelHost(hostname)) {
      if (__DEV__) {
        console.warn(
          `[API] Detected Expo tunnel host (${hostname}). Expo tunnel does not forward FastAPI port ${DEFAULT_API_PORT}. ` +
            `For remote testing, set EXPO_PUBLIC_API_URL or run in LAN mode on the same Wi-Fi (npx expo start).`
        );
      }
      // Return localhost fallback for tunnel mode when no explicit EXPO_PUBLIC_API_URL is configured
      return `http://localhost:${DEFAULT_API_PORT}${DEFAULT_API_PATH}`;
    }

    // Valid LAN / development host detected automatically from Expo runtime
    return `http://${hostname}:${DEFAULT_API_PORT}${DEFAULT_API_PATH}`;
  }

  // 4. Default development fallback
  if (currentPlatform === 'android') {
    return `http://10.0.2.2:${DEFAULT_API_PORT}${DEFAULT_API_PATH}`;
  }

  return `http://localhost:${DEFAULT_API_PORT}${DEFAULT_API_PATH}`;
}

let activeBaseUrl: string = resolveApiBaseUrl();

// Log resolved base URL once in development mode without exposing any secrets
if (__DEV__) {
  console.log(`[API] Resolved base URL: ${activeBaseUrl}`);
}

/**
 * Returns the currently active API base URL.
 */
export function getApiBaseUrl(): string {
  return activeBaseUrl;
}

/**
 * Programmatically overrides the active API base URL at runtime.
 */
export function setBaseUrl(url: string): void {
  activeBaseUrl = url;
  if (__DEV__) {
    console.log(`[API] Updated base URL: ${activeBaseUrl}`);
  }
}
