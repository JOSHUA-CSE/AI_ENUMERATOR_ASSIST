import { useAuthStore, User } from './authStore';

export type { User };

export interface Session {
  token: string;
  user: User;
}

type SessionListener = (session: Session | null) => void;
const listeners = new Set<SessionListener>();

// Sync listeners with authStore changes
useAuthStore.subscribe((state) => {
  const session: Session | null =
    state.status === 'authenticated' && state.user && state.token
      ? { token: state.token, user: state.user }
      : null;
  listeners.forEach((listener) => listener(session));
});

export const sessionService = {
  subscribe(listener: SessionListener) {
    listeners.add(listener);
    const session = this.getCurrentSession();
    listener(session);
    return () => {
      listeners.delete(listener);
    };
  },

  emitChange() {
    const session = this.getCurrentSession();
    listeners.forEach((listener) => listener(session));
  },

  async login(username: string, password: string): Promise<Session> {
    const user = await useAuthStore.getState().login(username, password);
    const token = useAuthStore.getState().token || '';
    const session: Session = { token, user };
    this.emitChange();
    return session;
  },

  async restoreSession(): Promise<Session | null> {
    const user = await useAuthStore.getState().restoreSession();
    const token = useAuthStore.getState().token;
    if (user && token) {
      const session: Session = { token, user };
      this.emitChange();
      return session;
    }
    this.emitChange();
    return null;
  },

  async logout(): Promise<void> {
    await useAuthStore.getState().logout();
    this.emitChange();
  },

  getCurrentSession(): Session | null {
    const state = useAuthStore.getState();
    if (state.status === 'authenticated' && state.user && state.token) {
      return { token: state.token, user: state.user };
    }
    return null;
  },

  isSessionInitialized(): boolean {
    const status = useAuthStore.getState().status;
    return status !== 'idle' && status !== 'initializing';
  },

  reset(): void {
    useAuthStore.getState().reset();
    listeners.clear();
  },
};
