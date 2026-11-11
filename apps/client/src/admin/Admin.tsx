import { type FormEvent, useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api, jsonBody } from '../api';
import type {
  ApplicationSettingsView,
  DiscoveredDeviceView,
  LibrarySyncStatus,
  MovieNightInput,
  MovieNightView,
  MoviePage,
  MovieSummary,
  SessionView,
  TmdbMovie,
} from '../contracts.generated';

function nextFriday() {
  const date = new Date();
  const delta = (5 - date.getDay() + 7) % 7 || 7;
  date.setDate(date.getDate() + delta);
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
}

function dateLabel(value: string, showtime: string | null) {
  const date = new Date(`${value}T12:00:00`);
  const label = date.toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' });
  if (!showtime) return label;
  const time = new Date(`2000-01-01T${showtime}`).toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' });
  return `${label} · ${time}`;
}

export function Admin() {
  const [session, setSession] = useState<SessionView | null>(null);
  const [settings, setSettings] = useState<ApplicationSettingsView | null>(null);
  const [devices, setDevices] = useState<DiscoveredDeviceView[]>([]);
  const [movies, setMovies] = useState<MovieSummary[]>([]);
  const [nights, setNights] = useState<MovieNightView[]>([]);
  const [sync, setSync] = useState<LibrarySyncStatus | null>(null);
  const [query, setQuery] = useState('');
  const [source, setSource] = useState('');
  const [rotationFilter, setRotationFilter] = useState('');
  const [moviePage, setMoviePage] = useState(1);
  const [movieTotal, setMovieTotal] = useState(0);
  const [selectedMovie, setSelectedMovie] = useState<number | null>(null);
  const [eventDate, setEventDate] = useState(nextFriday());
  const [showtime, setShowtime] = useState('');
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');
  const [tmdb, setTmdb] = useState<TmdbMovie[]>([]);

  const load = useCallback(async () => {
    try {
      const [nextSession, nextSettings, nextDevices, nextMovies, nextNights, nextSync] = await Promise.all([
        api<SessionView>('/api/session'), api<ApplicationSettingsView>('/api/settings'),
        api<DiscoveredDeviceView[]>('/api/devices'), api<MoviePage>(`/api/movies?query=${encodeURIComponent(query)}&source=${source}&rotation=${rotationFilter}&page=${moviePage}&page_size=20`),
        api<MovieNightView[]>('/api/movie-nights'), api<LibrarySyncStatus | null>('/api/library-sync'),
      ]);
      setSession(nextSession); setSettings(nextSettings); setDevices(nextDevices);
      setMovies(nextMovies.items); setMovieTotal(nextMovies.total); setNights(nextNights); setSync(nextSync); setError('');
      if (selectedMovie == null && nextMovies.items[0]) setSelectedMovie(nextMovies.items[0].id);
    } catch (caught) { setError(caught instanceof Error ? caught.message : 'Could not load settings.'); }
  }, [moviePage, query, rotationFilter, selectedMovie, source]);

  useEffect(() => { void load(); }, [load]);

  async function perform(action: () => Promise<unknown>, message: string) {
    try { setError(''); await action(); setNotice(message); await load(); }
    catch (caught) { setError(caught instanceof Error ? caught.message : 'Request failed.'); }
  }

  async function schedule(event: FormEvent) {
    event.preventDefault();
    if (!selectedMovie) return;
    const payload: MovieNightInput = { movie_id: selectedMovie, event_date: eventDate, showtime: showtime || null };
    await perform(() => api('/api/movie-nights', { method: 'POST', body: jsonBody(payload) }), 'Movie night scheduled.');
  }

  async function upload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    await perform(() => api('/api/movies/manual', { method: 'POST', body: data }), 'Poster added.');
    form.reset();
  }

  async function saveSettings(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!settings) return;
    await perform(() => api('/api/settings', {
      method: 'PUT',
      body: jsonBody({
        rotation: settings.rotation,
        slideshow_interval_seconds: settings.slideshow_interval_seconds,
        timezone: settings.timezone,
      }),
    }), 'Display settings saved.');
  }

  async function saveRoles(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!settings) return;
    await perform(() => api('/api/devices/roles', {
      method: 'PUT',
      body: jsonBody({ player_serial: settings.player_serial, library_serial: settings.library_serial, manual_host: settings.manual_host }),
    }), 'Device roles saved.');
  }

  async function tmdbSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const value = String(data.get('tmdb_query') || '');
    try { setTmdb(await api<TmdbMovie[]>(`/api/tmdb/search?query=${encodeURIComponent(value)}`)); }
    catch (caught) { setError(caught instanceof Error ? caught.message : 'TMDB search failed.'); }
  }

  return (
    <main className="admin-shell">
      <header className="admin-header">
        <div className="admin-brand"><span className="brand-mark">H</span><div><strong>Home Movie Poster</strong><small>Control room</small></div></div>
        <div className="header-actions"><span className={`live-pill ${devices.length ? 'ready' : ''}`}><i />{devices.length ? 'Kaleidescape online' : 'Discovering'}</span><Link className="button quiet" to="/display">Open display <span aria-hidden="true">↗</span></Link></div>
      </header>
      <section className="admin-hero">
        <div><p className="eyebrow">Tonight starts here</p><h1>Movie night,<br /><em>beautifully queued.</em></h1><p className="hero-copy">Schedule the feature, curate the collection, and let Kaleidescape take over when playback begins.</p></div>
        <div className="hero-stats"><div><strong>{nights.length}</strong><span>Scheduled</span></div><div><strong>{movieTotal}</strong><span>Posters</span></div><div><strong>{devices.length}</strong><span>Devices</span></div></div>
      </section>
      <p className="trust-note"><span>Private by design</span> Trusted LAN only. This control panel has no login and should never be exposed to the public internet.</p>
      {error && <p className="alert error" role="alert">{error}</p>}
      {notice && <p className="alert success">{notice}</p>}

      <div className="admin-grid">
        <section className="card feature-card">
          <div className="card-heading"><div><p className="eyebrow">Friday movie</p><h2>Schedule a screening</h2></div><span className="step">01</span></div>
          <form onSubmit={schedule} className="form-stack">
            <label>Movie<select value={selectedMovie ?? ''} onChange={(event) => setSelectedMovie(Number(event.target.value))} required>
              {movies.map((movie) => <option key={movie.id} value={movie.id}>{movie.title}{movie.year ? ` (${movie.year})` : ''}</option>)}
            </select></label>
            <div className="field-row"><label>Date<input type="date" value={eventDate} onChange={(event) => setEventDate(event.target.value)} required /></label>
              <label>Showtime <span className="optional">optional</span><input type="time" value={showtime} onChange={(event) => setShowtime(event.target.value)} /></label></div>
            <div className="button-row"><button type="button" className="button quiet" onClick={() => setEventDate(nextFriday())}>Next Friday</button><button className="button primary">Save movie night</button></div>
          </form>
          <div className="queue">
            {nights.length === 0 && <p className="muted">No screenings scheduled.</p>}
            {nights.map((night) => <article className="queue-item" key={night.id}>
              <div className="poster-thumb">{night.movie.poster_url ? <img src={night.movie.poster_url} alt="" /> : <span>MP</span>}</div>
              <div><strong>{night.movie.title}</strong><small>{dateLabel(night.event_date, night.showtime)}</small></div>
              <button className="icon-button" aria-label={`Delete ${night.movie.title}`} onClick={() => void perform(() => api(`/api/movie-nights/${night.id}`, { method: 'DELETE' }), 'Movie night removed.')}>×</button>
            </article>)}
          </div>
        </section>

        <section className="card">
          <div className="card-heading"><div><p className="eyebrow">Library</p><h2>Posters</h2></div><span className="count">{movieTotal}</span></div>
          <input className="search" type="search" placeholder="Search your movies" value={query} onChange={(event) => { setQuery(event.target.value); setMoviePage(1); }} />
          <div className="library-filters"><select aria-label="Movie source" value={source} onChange={(event) => { setSource(event.target.value); setMoviePage(1); }}><option value="">All sources</option><option value="kaleidescape">Kaleidescape</option><option value="tmdb">TMDB</option><option value="manual">Manual</option></select><select aria-label="Rotation filter" value={rotationFilter} onChange={(event) => { setRotationFilter(event.target.value); setMoviePage(1); }}><option value="">Any rotation state</option><option value="included">In rotation</option><option value="excluded">Excluded</option></select></div>
          <div className="movie-list">
            {movies.map((movie) => <article className="movie-row" key={movie.id}>
              <div className="poster-thumb">{movie.poster_url ? <img src={movie.poster_url} alt="" /> : <span>MP</span>}</div>
              <div className="grow"><strong>{movie.title}</strong><small>{movie.year || 'Year unknown'} · {movie.source}</small></div>
              <label className="replace-poster" title="Replace poster">↥<input type="file" accept="image/jpeg,image/png,image/webp" onChange={(event) => {
                const poster = event.target.files?.[0];
                if (!poster) return;
                const data = new FormData();
                data.append('poster', poster);
                void perform(() => api(`/api/movies/${movie.id}/poster`, { method: 'POST', body: data }), 'Poster replaced.');
              }} /><span className="sr-only">Replace {movie.title} poster</span></label>
              <label className="switch"><input type="checkbox" checked={movie.include_in_rotation} onChange={() => void perform(() => api(`/api/movies/${movie.id}`, { method: 'PATCH', body: jsonBody({ include_in_rotation: !movie.include_in_rotation }) }), 'Rotation updated.')} /><span /></label>
            </article>)}
          </div>
          <div className="pagination"><button className="button quiet" disabled={moviePage <= 1} onClick={() => setMoviePage((value) => Math.max(1, value - 1))}>Previous</button><span>Page {moviePage} of {Math.max(1, Math.ceil(movieTotal / 20))}</span><button className="button quiet" disabled={moviePage * 20 >= movieTotal} onClick={() => setMoviePage((value) => value + 1)}>Next</button></div>
          <details><summary>Add a manual poster</summary><form onSubmit={upload} className="form-stack inset">
            <label>Title<input name="title" required maxLength={300} /></label><label>Year <span className="optional">optional</span><input name="year" type="number" min="1888" max="2200" /></label>
            <label>Poster JPEG or PNG<input name="poster" type="file" accept="image/jpeg,image/png,image/webp" required /></label><button className="button primary">Add poster</button>
          </form></details>
        </section>

        <section className="card">
          <div className="card-heading"><div><p className="eyebrow">Kaleidescape</p><h2>Devices</h2></div><span className={`status-chip ${devices.length ? 'ready' : ''}`}>{devices.length ? `${devices.length} found` : 'Searching'}</span></div>
          {devices.length === 0 && <div className="device-empty"><span className="radar-icon"><i /></span><div><strong>No player found yet</strong><p>Discovery is scanning this LAN. On Windows, stop the Docker monitor and run <code>uv run poster monitor</code> natively. You can also enter a hostname below.</p></div></div>}
          <form onSubmit={saveRoles} className="form-stack">
            <label>Playback player<select value={settings?.player_serial || ''} onChange={(event) => settings && setSettings({ ...settings, player_serial: event.target.value })}><option value="">Auto-select</option>{devices.filter((device) => device.supports_playback).map((device) => <option value={device.serial_number} key={device.serial_number}>{device.friendly_name || device.serial_number}</option>)}</select></label>
            <label>Library host<select value={settings?.library_serial || ''} onChange={(event) => settings && setSettings({ ...settings, library_serial: event.target.value })}><option value="">Auto-select</option>{devices.filter((device) => device.supports_library).map((device) => <option value={device.serial_number} key={device.serial_number}>{device.friendly_name || device.serial_number}</option>)}</select></label>
            <label>Manual hostname <span className="optional">fallback</span><input value={settings?.manual_host || ''} onChange={(event) => settings && setSettings({ ...settings, manual_host: event.target.value })} placeholder="kplayer.local" /></label>
            <button className="button primary">Save device roles</button>
          </form>
          <div className="sync-row"><div><strong>Library sync</strong><small>{sync ? `${sync.status} · ${sync.updated_count} updated` : 'Not run yet'}</small></div><button className="button quiet" onClick={() => void perform(() => api('/api/library-sync', { method: 'POST' }), 'Library sync queued.')}>Sync now</button></div>
        </section>

        <section className="card">
          <div className="card-heading"><div><p className="eyebrow">Television</p><h2>Display settings</h2></div><span className="step">02</span></div>
          {settings && <form onSubmit={saveSettings} className="form-stack">
            <fieldset><legend>Rotation</legend><div className="segmented">{([0, 90, 270] as const).map((rotation) => <label key={rotation}><input type="radio" checked={settings.rotation === rotation} onChange={() => setSettings({ ...settings, rotation })} /><span>{rotation}°</span></label>)}</div></fieldset>
            <label>Poster interval <span>{settings.slideshow_interval_seconds}s</span><input type="range" min="10" max="300" step="5" value={settings.slideshow_interval_seconds} onChange={(event) => setSettings({ ...settings, slideshow_interval_seconds: Number(event.target.value) })} /></label>
            <label>Timezone<input value={settings.timezone} onChange={(event) => setSettings({ ...settings, timezone: event.target.value })} /></label>
            <button className="button primary">Save display settings</button>
          </form>}
        </section>

        {session?.tmdb_enabled && <section className="card full-card">
          <div className="card-heading"><div><p className="eyebrow">Optional source</p><h2>Search TMDB</h2></div></div>
          <form onSubmit={tmdbSearch} className="inline-form"><input name="tmdb_query" placeholder="Movie title" required /><button className="button quiet">Search</button></form>
          <div className="tmdb-results">{tmdb.map((movie) => <article className="movie-row" key={movie.id}><div className="poster-thumb">{movie.poster_url ? <img src={movie.poster_url} alt="" /> : <span>TM</span>}</div><div className="grow"><strong>{movie.title}</strong><small>{movie.year || 'Year unknown'}</small></div><button className="button quiet" onClick={() => void perform(() => api('/api/tmdb/import', { method: 'POST', body: jsonBody({ tmdb_id: movie.id }) }), 'TMDB poster imported.')}>Import</button></article>)}</div>
          <p className="credit">This product uses the TMDB API but is not endorsed or certified by TMDB.</p>
        </section>}
      </div>
    </main>
  );
}
