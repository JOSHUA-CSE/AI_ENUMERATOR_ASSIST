import * as SecureStore from 'expo-secure-store';

const TOKEN_KEY = 'ai_enumerator_auth_token';

// In-memory store fallback for environments where SecureStore is not available (like non-native/tests)
const memoryStore: Record<string, string> = {};

function getWebStorage(): Storage | null {
  try {
    if (typeof globalThis !== 'undefined' && 'localStorage' in globalThis) {
      return (globalThis as any).localStorage;
    }
  } catch {
    // Ignore error in environments where localStorage is restricted
  }
  return null;
}

export const secureStore = {
  async setToken(token: string): Promise<boolean> {
    try {
      const storage = getWebStorage();
      if (storage) {
        storage.setItem(TOKEN_KEY, token);
      }
      await SecureStore.setItemAsync(TOKEN_KEY, token);
      return true;
    } catch {
      memoryStore[TOKEN_KEY] = token;
      return true;
    }
  },

  async getToken(): Promise<string | null> {
    try {
      const token = await SecureStore.getItemAsync(TOKEN_KEY);
      if (token) {
        return token;
      }
      const storage = getWebStorage();
      if (storage) {
        const webToken = storage.getItem(TOKEN_KEY);
        if (webToken) return webToken;
      }
      return memoryStore[TOKEN_KEY] || null;
    } catch {
      const storage = getWebStorage();
      if (storage) {
        const webToken = storage.getItem(TOKEN_KEY);
        if (webToken) return webToken;
      }
      return memoryStore[TOKEN_KEY] || null;
    }
  },

  async clearToken(): Promise<boolean> {
    try {
      const storage = getWebStorage();
      if (storage) {
        storage.removeItem(TOKEN_KEY);
      }
      await SecureStore.deleteItemAsync(TOKEN_KEY);
      delete memoryStore[TOKEN_KEY];
      return true;
    } catch {
      delete memoryStore[TOKEN_KEY];
      return true;
    }
  },
};
