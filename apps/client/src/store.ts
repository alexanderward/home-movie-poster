import { create } from 'zustand';
import { api } from './api';
import type { DisplayState } from './contracts.generated';

/** `/display?preview=slideshow` shows the idle slideshow even while a movie night or playback would win. */
export const isSlideshowPreview = () => new URLSearchParams(window.location.search).get('preview') === 'slideshow';

interface DisplayStore {
  state: DisplayState | null;
  error: string;
  connected: boolean;
  refresh: () => Promise<void>;
  connect: () => () => void;
}

let reconnectTimer: number | undefined;

export const useDisplayStore = create<DisplayStore>((set, get) => ({
  state: null,
  error: '',
  connected: false,
  refresh: async () => {
    try {
      const state = await api<DisplayState>(isSlideshowPreview() ? '/api/display?preview=slideshow' : '/api/display');
      set({ state, error: '' });
    } catch (error) {
      set({ error: error instanceof Error ? error.message : 'Display unavailable' });
    }
  },
  connect: () => {
    if (isSlideshowPreview()) {
      // The websocket pushes the live TV state, so a preview polls its own state instead.
      void get().refresh();
      const timer = window.setInterval(() => void get().refresh(), 3000);
      return () => window.clearInterval(timer);
    }
    let socket: WebSocket | null = null;
    let stopped = false;
    const poll = window.setInterval(() => {
      if (!get().connected) void get().refresh();
    }, 5000);
    const open = () => {
      if (stopped || !('WebSocket' in window)) return;
      const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
      socket = new WebSocket(`${protocol}://${window.location.host}/api/display/socket`);
      socket.onopen = () => set({ connected: true });
      socket.onmessage = (message) => {
        try { set({ state: JSON.parse(message.data) as DisplayState, error: '' }); } catch { /* poll recovers */ }
      };
      socket.onerror = () => socket?.close();
      socket.onclose = () => {
        set({ connected: false });
        if (!stopped) reconnectTimer = window.setTimeout(open, 5000);
      };
    };
    void get().refresh();
    open();
    return () => {
      stopped = true;
      window.clearInterval(poll);
      if (reconnectTimer) window.clearTimeout(reconnectTimer);
      socket?.close();
    };
  },
}));
