import fs from 'fs';
import path from 'path';
import {
  extractHostname,
  isTunnelHost,
  resolveApiBaseUrl,
  getApiBaseUrl,
  setBaseUrl,
  DEFAULT_API_PORT,
  DEFAULT_API_PATH,
} from '../src/core/networkConfig';

describe('Network Configuration & Dynamic Host Resolution', () => {
  const originalEnv = process.env.EXPO_PUBLIC_API_URL;

  afterEach(() => {
    process.env.EXPO_PUBLIC_API_URL = originalEnv;
  });

  describe('extractHostname', () => {
    it('extracts IPv4 address from hostUri with Metro port (172.17.4.177:8081)', () => {
      const result = extractHostname('172.17.4.177:8081');
      expect(result).toBe('172.17.4.177');
    });

    it('extracts IPv4 address from hostUri with alternate Expo port (10.132.120.48:19000)', () => {
      const result = extractHostname('10.132.120.48:19000');
      expect(result).toBe('10.132.120.48');
    });

    it('extracts hostname when no port is attached (192.168.1.50)', () => {
      const result = extractHostname('192.168.1.50');
      expect(result).toBe('192.168.1.50');
    });

    it('strips protocol and path from full URL string (http://192.168.1.15:8081/subpath?foo=bar)', () => {
      const result = extractHostname('http://192.168.1.15:8081/subpath?foo=bar');
      expect(result).toBe('192.168.1.15');
    });

    it('strips exp:// protocol prefix (exp://10.0.0.5:8081)', () => {
      const result = extractHostname('exp://10.0.0.5:8081');
      expect(result).toBe('10.0.0.5');
    });

    it('returns null for empty or invalid inputs', () => {
      expect(extractHostname('')).toBeNull();
      expect(extractHostname('   ')).toBeNull();
      expect(extractHostname(null)).toBeNull();
      expect(extractHostname(undefined)).toBeNull();
    });
  });

  describe('isTunnelHost', () => {
    it('identifies exp.direct tunnel hosts', () => {
      expect(isTunnelHost('u87a-10-132-120-48.exp.direct')).toBe(true);
      expect(isTunnelHost('test.exp.direct')).toBe(true);
    });

    it('identifies ngrok tunnel hosts', () => {
      expect(isTunnelHost('abc-123.ngrok.io')).toBe(true);
      expect(isTunnelHost('abc-123.ngrok-free.app')).toBe(true);
      expect(isTunnelHost('abc-123.ngrok.app')).toBe(true);
    });

    it('identifies other tunnel domains (loca.lt, tunnel.expo.dev)', () => {
      expect(isTunnelHost('myapp.loca.lt')).toBe(true);
      expect(isTunnelHost('tunnel.expo.dev')).toBe(true);
    });

    it('returns false for standard LAN IP addresses and localhost', () => {
      expect(isTunnelHost('172.17.4.177')).toBe(false);
      expect(isTunnelHost('10.132.120.48')).toBe(false);
      expect(isTunnelHost('192.168.1.100')).toBe(false);
      expect(isTunnelHost('localhost')).toBe(false);
      expect(isTunnelHost('127.0.0.1')).toBe(false);
    });
  });

  describe('resolveApiBaseUrl', () => {
    it('derives FastAPI URL using port 8000 when Expo host is 172.17.4.177:8081 (Wi-Fi B)', () => {
      delete process.env.EXPO_PUBLIC_API_URL;
      const url = resolveApiBaseUrl({
        hostUri: '172.17.4.177:8081',
        platformOS: 'ios',
      });
      expect(url).toBe('http://172.17.4.177:8000/api/v1');
      // Verify Metro port 8081 is NEVER used as API port
      expect(url).not.toContain(':8081');
    });

    it('derives FastAPI URL using port 8000 when Expo host is 10.132.120.48:8081 (Wi-Fi A)', () => {
      delete process.env.EXPO_PUBLIC_API_URL;
      const url = resolveApiBaseUrl({
        hostUri: '10.132.120.48:8081',
        platformOS: 'android',
      });
      expect(url).toBe('http://10.132.120.48:8000/api/v1');
    });

    it('prioritizes EXPO_PUBLIC_API_URL when explicitly configured', () => {
      const explicitUrl = 'http://example.test:8000/api/v1';
      process.env.EXPO_PUBLIC_API_URL = explicitUrl;
      const url = resolveApiBaseUrl({
        hostUri: '172.17.4.177:8081',
        envUrl: explicitUrl,
      });
      expect(url).toBe('http://example.test:8000/api/v1');
    });

    it('does NOT construct http://something.exp.direct:8000/api/v1 in tunnel mode', () => {
      delete process.env.EXPO_PUBLIC_API_URL;
      const url = resolveApiBaseUrl({
        hostUri: 'u87a-tunnel.exp.direct:80',
        platformOS: 'ios',
      });
      // In tunnel mode, must not use exp.direct with port 8000
      expect(url).not.toContain('exp.direct:8000');
      expect(url).toBe('http://localhost:8000/api/v1');
    });

    it('resolves localhost for web platform on localhost', () => {
      delete process.env.EXPO_PUBLIC_API_URL;
      const url = resolveApiBaseUrl({
        platformOS: 'web',
        webHostname: 'localhost',
      });
      expect(url).toBe('http://localhost:8000/api/v1');
    });

    it('resolves remote domain for web platform hosted remotely', () => {
      delete process.env.EXPO_PUBLIC_API_URL;
      const url = resolveApiBaseUrl({
        platformOS: 'web',
        webHostname: 'app.example.com',
      });
      expect(url).toBe('http://app.example.com:8000/api/v1');
    });

    it('handles null/missing host gracefully', () => {
      delete process.env.EXPO_PUBLIC_API_URL;
      const url = resolveApiBaseUrl({
        hostUri: null,
        platformOS: 'ios',
      });
      expect(url).toBe('http://localhost:8000/api/v1');
    });

    it('handles Android emulator fallback when host is null', () => {
      delete process.env.EXPO_PUBLIC_API_URL;
      const url = resolveApiBaseUrl({
        hostUri: null,
        platformOS: 'android',
      });
      expect(url).toBe('http://10.0.2.2:8000/api/v1');
    });
  });

  describe('setBaseUrl and getApiBaseUrl', () => {
    it('allows runtime override of base URL', () => {
      const customUrl = 'http://staging-server:8000/api/v1';
      setBaseUrl(customUrl);
      expect(getApiBaseUrl()).toBe(customUrl);
    });
  });

  describe('Source Code Integrity - No Hardcoded LAN IPs', () => {
    it('verifies mobile/src/core/apiClient.ts contains no hardcoded currentLanIp', () => {
      const filePath = path.join(__dirname, '../src/core/apiClient.ts');
      const content = fs.readFileSync(filePath, 'utf-8');

      expect(content).not.toContain('currentLanIp');
      expect(content).not.toMatch(/const\s+currentLanIp\s*=/);
      // Ensure no specific hardcoded LAN addresses exist as literal values in logic
      expect(content).not.toContain("'172.17.");
      expect(content).not.toContain("'10.132.");
      expect(content).not.toContain("'192.168.");
    });
  });
});
