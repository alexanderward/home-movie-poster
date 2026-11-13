import { useEffect, useRef, useState, type ReactNode } from 'react';
import { isSlideshowPreview, useDisplayStore } from '../store';
import { calculateProgress } from '../progress';
import { startAutoReload } from './autoReload';
// Bundled so the TV renders the same type offline instead of falling back to its system fonts.
import '@fontsource/bebas-neue/400.css';
import '@fontsource/inter/500.css';
import '@fontsource/inter/600.css';

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
      <div className="poster-frame">
        {slide.url ? <img src={slide.url} alt={`${slide.title} poster`} /> : <div className="poster-empty"><span>{slide.title}</span></div>}
      </div>
    </div>
  );
}

/**
 * The date part of the billing line, saying only what the headline doesn't: nothing for "Tonight", the month and day
 * when the headline already names the weekday or "Tomorrow", and the full date behind "Coming Soon".
 */
function formatDay(value: string | null) {
  if (!value) return '';
  const date = new Date(`${value}T12:00:00`);
  const today = new Date();
  today.setHours(12, 0, 0, 0);
  const daysAway = Math.round((date.getTime() - today.getTime()) / 86_400_000);
  if (daysAway <= 0) return '';
  return date.toLocaleDateString(undefined, daysAway < 7
    ? { month: 'long', day: 'numeric' }
    : { weekday: 'short', month: 'short', day: 'numeric' });
}

function formatTime(showtime: string | null) {
  return showtime
    ? new Date(`2000-01-01T${showtime}`).toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' })
    : '';
}

function formatRuntime(seconds: number) {
  const total = Math.max(0, Math.round(seconds / 60));
  const hours = Math.floor(total / 60);
  const minutes = total % 60;
  return hours ? `${hours}h ${String(minutes).padStart(2, '0')}m` : `${minutes}m`;
}

/** Top band: the headline centered between two gold rules, like the letters on a marquee. It says *when*. */
function Marquee({ text, live }: { text: string; live: boolean }) {
  // A collection can hide its headline; the band stays (keeping the poster centered) but goes black.
  if (!text) return <header className="marquee" />;
  return (
    <header className="marquee">
      <span className="marquee-rule" aria-hidden="true" />
      <h1 key={text} className="marquee-title">
        {live && <span className="live-dot" aria-hidden="true" />}
        {text}
      </h1>
      <span className="marquee-rule" aria-hidden="true" />
    </header>
  );
}

/**
 * Bottom band: only what the poster and headline can't say (the poster already carries the title). Left empty when
 * there's nothing to add, so the poster stands alone.
 */
function Billing({ children }: { children?: ReactNode }) {
  return <footer className="billing">{children}</footer>;
}

function Showtime({ day, time }: { day: string; time: string }) {
  if (!day && !time) return null;
  return (
    <p key={`${day}|${time}`} className="billing-line">
      {day && <span>{day}</span>}
      {day && time && <span className="billing-sep" aria-hidden="true" />}
      {time && <strong>{time}</strong>}
    </p>
  );
}

function Playback({ progress, duration }: { progress: number; duration: number }) {
  const elapsed = duration * (progress / 100);
  return (
    <div className="billing-line billing-playback">
      <span>{formatRuntime(elapsed)}</span>
      <div className="billing-progress" role="progressbar" aria-valuenow={Math.round(progress)} aria-valuemin={0} aria-valuemax={100} aria-label={`${Math.round(progress)} percent watched`}>
        <span style={{ width: `${progress}%` }} />
      </div>
      <strong>{formatRuntime(duration - elapsed)} left</strong>
    </div>
  );
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
  if (!state) return <main className="display-loading">{error || 'Preparing your display…'}</main>;
  const rotated = state.rotation !== 0;

  if (state.mode === 'setup') {
    return (
      <main className={`display-shell rotation-${state.rotation}`}>
        <section className={`display-canvas setup-canvas ${rotated ? 'is-rotated' : ''}`}>
          <div className="setup-orb setup-orb-one" />
          <div className="setup-orb setup-orb-two" />
          <header className="display-brand">
            <span className="brand-mark">F</span>
            <span>Frame</span>
          </header>
          <div className="setup-content">
            <div className="setup-kicker"><span className={`connection-dot ${connected ? 'online' : ''}`} /> Display ready</div>
            <h1>Your wall deserves something to show.</h1>
            <p>Create a collection, add posters or artwork, and show it on the TV from the admin page.</p>
            <div className="setup-route"><span>Open on your phone</span><strong>/admin</strong></div>
          </div>
          <footer className="setup-footer"><span>Waiting for a collection</span><span>Trusted LAN only</span></footer>
        </section>
      </main>
    );
  }

  return (
    <main className={`display-shell rotation-${state.rotation}`}>
      <section className={`display-canvas theater ${rotated ? 'is-rotated' : ''}`}>
        <Marquee text={state.headline} live={state.mode === 'now_playing' && state.playback_status === 'playing'} />
        <div className="stage">
          {layers.map((layer) => <SlideLayer key={layer.key} slide={layer} />)}
          {isSlideshowPreview() && <p className="preview-badge">Slideshow preview</p>}
        </div>
        <Billing>

          {state.mode === 'scheduled' && <Showtime day={formatDay(state.event_date)} time={formatTime(state.showtime)} />}
          {state.mode === 'now_playing' && state.duration_seconds ? <Playback progress={progress} duration={state.duration_seconds} /> : null}
        </Billing>
      </section>
    </main>
  );
}
