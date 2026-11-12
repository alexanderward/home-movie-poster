import { useEffect, useRef, useState } from 'react';
import { isSlideshowPreview, useDisplayStore } from '../store';
import { calculateProgress } from '../progress';
import { startAutoReload } from './autoReload';

/** Keep in sync with the `slide-in` animation duration in styles.css. */
const FADE_MS = 1800;

type Slide = { key: string; url: string | null; title: string };

/**
 * Stacks slides so a new poster fades in over the old one. The next image is
 * preloaded first so the fade never reveals a half-decoded poster.
 */
function useCrossfade(slide: Slide | null) {
  const [layers, setLayers] = useState<Slide[]>(() => (slide ? [slide] : []));
  const pending = useRef<string | null>(null);

  useEffect(() => {
    if (!slide || layers[layers.length - 1]?.key === slide.key || pending.current === slide.key) return;
    pending.current = slide.key;
    let cancelled = false;
    let cleanup: number | undefined;
    const show = () => {
      if (cancelled) return;
      cancelled = true;
      pending.current = null;
      setLayers((prev) => [...prev.slice(-1), slide]);
      cleanup = window.setTimeout(() => setLayers((prev) => prev.slice(-1)), FADE_MS + 100);
    };
    if (slide.url) {
      const img = new Image();
      img.onload = img.onerror = show;
      img.src = slide.url;
      if (img.complete) show();
    } else {
      show();
    }
    return () => {
      cancelled = true;
      pending.current = null;
      window.clearTimeout(cleanup);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [slide?.key]);

  return layers;
}

function SlideLayer({ slide }: { slide: Slide }) {
  return (
    <div className="slide">
      {slide.url && <div className="poster-ambient" aria-hidden="true"><img src={slide.url} alt="" /></div>}
      <div className="poster-frame">
        {slide.url ? <img src={slide.url} alt={`${slide.title} poster`} /> : <div className="poster-empty"><span>{slide.title}</span></div>}
      </div>
    </div>
  );
}

function formatDate(value: string | null, showtime: string | null) {
  if (!value && !showtime) return '';
  const date = value ? new Date(`${value}T12:00:00`) : null;
  const day = date?.toLocaleDateString(undefined, { weekday: 'long', month: 'long', day: 'numeric' });
  const time = showtime
    ? new Date(`2000-01-01T${showtime}`).toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' })
    : '';
  return [day, time].filter(Boolean).join(' · ');
}

export function Display() {
  const { state, error, connected, connect } = useDisplayStore();
  const [clock, tick] = useState(0);
  useEffect(() => connect(), [connect]);
  useEffect(() => startAutoReload(), []);
  useEffect(() => {
    const timer = window.setInterval(() => tick((value) => value + 1), 1000);
    return () => window.clearInterval(timer);
  }, []);
  const progress = state?.duration_seconds && state.position_seconds != null && state.observed_at
    ? calculateProgress(
      state.position_seconds,
      state.duration_seconds,
      state.observed_at,
      state.playback_status === 'playing',
      Date.now() + clock * 0,
    ) : 0;
  const slide = state && state.mode !== 'setup'
    ? { key: `${state.mode}|${state.poster_url ?? state.title}`, url: state.poster_url, title: state.title }
    : null;
  const layers = useCrossfade(slide);
  if (!state) return <main className="display-loading">{error || 'Preparing your poster display…'}</main>;
  const rotated = state.rotation !== 0;

  if (state.mode === 'setup') {
    return (
      <main className={`display-shell rotation-${state.rotation}`}>
        <section className={`display-canvas setup-canvas ${rotated ? 'is-rotated' : ''}`}>
          <div className="setup-orb setup-orb-one" />
          <div className="setup-orb setup-orb-two" />
          <header className="display-brand">
            <span className="brand-mark">H</span>
            <span>Home Movie Poster</span>
          </header>
          <div className="setup-content">
            <div className="setup-kicker"><span className={`connection-dot ${connected ? 'online' : ''}`} /> Display ready</div>
            <h1>Your cinema deserves an opening night.</h1>
            <p>Connect Strato or choose your first movie from the admin page.</p>
            <div className="setup-route"><span>Open on your phone</span><strong>/admin</strong></div>
          </div>
          <footer className="setup-footer"><span>Waiting for a poster</span><span>Trusted LAN only</span></footer>
        </section>
      </main>
    );
  }

  return (
    <main className={`display-shell rotation-${state.rotation}`}>
      <section className={`display-canvas ${rotated ? 'is-rotated' : ''}`}>
        {layers.map((layer) => <SlideLayer key={layer.key} slide={layer} />)}
        {isSlideshowPreview() && <p className="preview-badge">Slideshow preview</p>}
        {state.mode === 'scheduled' && formatDate(state.event_date, state.showtime) && (
          <p key={formatDate(state.event_date, state.showtime)} className="showtime">{formatDate(state.event_date, state.showtime)}</p>
        )}
        {state.mode === 'now_playing' && state.duration_seconds && (
          <div className="progress" aria-label={`${Math.round(progress)} percent watched`}><span style={{ width: `${progress}%` }} /></div>
        )}
      </section>
    </main>
  );
}
