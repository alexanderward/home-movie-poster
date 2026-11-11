import { useEffect, useState } from 'react';
import { useDisplayStore } from '../store';
import { calculateProgress } from '../progress';

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
            <p>Connect Kaleidescape or add your first poster from the admin page.</p>
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
        {state.poster_url && <div className="poster-ambient" aria-hidden="true"><img src={state.poster_url} alt="" /></div>}
        <header className="display-brand display-brand-overlay"><span className="brand-mark">H</span><span>Home Movie Poster</span></header>
        <div className="poster-frame">
          {state.poster_url ? <img src={state.poster_url} alt={`${state.title} poster`} /> : <div className="poster-empty"><span>HOME CINEMA</span></div>}
        </div>
        <div className="display-copy">
          <div className="eyebrow-row">
            <p className="eyebrow">{state.headline}</p>
            <span className={`connection-dot ${connected ? 'online' : ''}`} aria-label={connected ? 'Live' : 'Polling'} />
          </div>
          <h1>{state.title}</h1>
          {state.playback_status === 'paused' && <p className="paused">Paused</p>}
          <p className="showtime">{formatDate(state.event_date, state.showtime)}</p>
          {state.mode === 'now_playing' && state.duration_seconds && (
            <div className="progress" aria-label={`${Math.round(progress)} percent watched`}><span style={{ width: `${progress}%` }} /></div>
          )}
        </div>
      </section>
    </main>
  );
}
