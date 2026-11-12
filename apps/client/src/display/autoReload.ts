/**
 * Keeps the TV on the latest client code so nobody has to walk to the screen after a change.
 *
 * - Dev server: Vite already pushes edits over its HMR WebSocket. The display reloads fully on each update instead of
 *   patching in place, so crossfade layers and keyframe animations restart cleanly.
 * - Built bundle: there is no push channel, so the display re-fetches its own HTML. Vite fingerprints asset names, so
 *   any rebuild changes that HTML; when it differs from what this page booted with, the page reloads.
 */
const CHECK_MS = 30_000;

async function fetchShell() {
  const response = await fetch(window.location.pathname, { cache: 'no-store', credentials: 'same-origin' });
  if (!response.ok) return null;
  const html = await response.text();
  // Only trust a real app shell, never an error page served mid-restart.
  return html.includes('id="root"') ? html : null;
}

export function startAutoReload(): () => void {
  if (import.meta.hot) {
    const reload = () => window.location.reload();
    import.meta.hot.on('vite:beforeUpdate', reload);
    return () => import.meta.hot?.off('vite:beforeUpdate', reload);
  }

  let stopped = false;
  let booted: string | null = null;
  let timer: number | undefined;
  const check = async () => {
    try {
      const html = await fetchShell();
      if (html && booted == null) booted = html;
      else if (html && html !== booted) { window.location.reload(); return; }
    } catch {
      // Server restarting or the network blipped; try again next round.
    }
    if (!stopped) timer = window.setTimeout(check, CHECK_MS);
  };
  void check();
  return () => {
    stopped = true;
    window.clearTimeout(timer);
  };
}
