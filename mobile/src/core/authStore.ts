import { create } from 'zustand';
import { apiClient, setUnauthorizedCallback, setAuthToken } from './apiClient';
import { secureStore } from './secureStore';

export interface User {
  id: string;
  name: string;
  username: string;
  role: 'DEPUTY_TAHSILDAR' | 'SUPERVISOR' | 'ENUMERATOR';
}

export type AuthStatus = 'idle' | 'initializing' | 'authenticated' | 'unauthenticated';

interface AuthState {
  status: AuthStatus;
  user: User | null;
  token: string | null;
  error: string | null;
  restoreSession: () => Promise<User | null>;
  login: (username: string, password: string) => Promise<User>;
  logout: () => Promise<void>;
  clearError: () => void;
  reset: () => void;
}

export const useAuthStore = create<AuthState>((set, get) => ({
  status: 'idle',
  user: null,
  token: null,
  error: null,

  restoreSession: async () => {
    // If already initialized and authenticated, return existing user
    if (get().status === 'authenticated' && get().user) {
      return get().user;
    }

    set({ status: 'initializing', error: null });

    try {
      const token = await secureStore.getToken();
      if (!token) {
        setAuthToken(null);
        set({ status: 'unauthenticated', user: null, token: null });
        return null;
      }

      setAuthToken(token);
      // Authoritative verification via backend GET /auth/me
      const user = await apiClient.get<User>('/auth/me');
      set({ status: 'authenticated', user, token, error: null });
      return user;
    } catch (error: any) {
      setAuthToken(null);
      // Cleanly transition to unauthenticated on session restore failure (e.g. expired token, canceled request)
      if (error && (error.status === 401 || error.status === 403)) {
        await secureStore.clearToken();
      }
      set({ status: 'unauthenticated', user: null, token: null });
      return null;
    }
  },

  login: async (username: string, password: string) => {
    set({ error: null });
    try {
      const response = await apiClient.post<any>('/auth/login', {
        username,
        password,
      });

      const token = response.access_token;
      const user: User = response.user;

      setAuthToken(token);
      await secureStore.setToken(token);
      set({ status: 'authenticated', user, token, error: null });
      return user;
    } catch (error: any) {
      const message = error.message || 'Login failed';
      set({ error: message });
      throw error;
    }
  },

  logout: async () => {
    try {
      const currentToken = get().token;
      if (currentToken) {
        await apiClient.post('/auth/logout', {});
      }
    } catch {
      // Ignore network errors during logout
    } finally {
      setAuthToken(null);
      await secureStore.clearToken();
      set({ status: 'unauthenticated', user: null, token: null, error: null });
    }
  },

  clearError: () => set({ error: null }),

  reset: () => {
    setAuthToken(null);
    set({ status: 'idle', user: null, token: null, error: null });
  },
}));

// Wire unauthorized 401 callback from apiClient
setUnauthorizedCallback(() => {
  useAuthStore.getState().logout();
});
