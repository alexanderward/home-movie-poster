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

export const useDisplayStore = create<DisplayStore>((set, get) => ({
  state: null,
  error: '',
  connected: false,
  refresh: async () => {
    try {
      const state = await api<DisplayState>(isSlideshowPreview() ? '/api/display?preview=slideshow' : '/api/display');
      set({ state, error: '', connected: true });
    } catch (error) {
      set({ error: error instanceof Error ? error.message : 'Display unavailable', connected: false });
    }
  },
  connect: () => {
    let stopped = false;
    let timer: number | undefined;
    const poll = async () => {
      await get().refresh();
      if (!stopped) timer = window.setTimeout(poll, isSlideshowPreview() ? 3000 : 1000);
    };
    void poll();
    return () => {
      stopped = true;
      if (timer) window.clearTimeout(timer);
    };
  },
}));
