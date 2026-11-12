import { type FormEvent, useCallback, useEffect, useRef, useState } from 'react';
import { api, jsonBody } from '../api';
import type { MovieDetail, MovieNightView, MovieSummary, PosterSearch, PosterSearchResult, SlideshowView } from '../contracts.generated';
import { PosterThumb, dateLabel, errorMessage, isoDate, nextFriday, type Notify, useDebounced } from './shared';

const SOURCE_LABELS: Record<PosterSearchResult['sources'][number], string> = {
  tmdb: 'TMDB',
  manual: 'Uploaded',
};

const TMDB_NOTES: Record<PosterSearch['tmdb'], string> = {
  ok: '',
  disabled: 'TMDB search is not configured. Add TMDB_READ_TOKEN to .env; uploaded and previously selected posters remain available.',
  unavailable: 'TMDB is unreachable right now. Showing uploaded and previously selected posters only.',
};

function intervalLabel(seconds: number) {
  if (seconds < 60) return `${seconds} seconds`;
  const minutes = seconds / 60;
  if (minutes === 1) return 'minute';
  return Number.isInteger(minutes) ? `${minutes} minutes` : `${seconds} seconds`;
}

/** The first Friday from next Friday onward that has no movie night yet. */
function nextFreeFriday(taken: Set<string>) {
  const date = new Date(`${nextFriday()}T12:00:00`);
  while (taken.has(isoDate(date))) date.setDate(date.getDate() + 7);
  return isoDate(date);
}

/** "Tonight", "Tomorrow" or "In N days" for the next two weeks; empty beyond that. */
function relativeDay(value: string) {
  const today = new Date(`${isoDate(new Date())}T12:00:00`);
  const days = Math.round((new Date(`${value}T12:00:00`).getTime() - today.getTime()) / 86_400_000);
  if (days <= 0) return 'Tonight';
  if (days === 1) return 'Tomorrow';
  return days < 14 ? `In ${days} days` : '';
}

function longDateLabel(value: string, showtime: string | null) {
  const label = new Date(`${value}T12:00:00`).toLocaleDateString(undefined, { weekday: 'long', month: 'long', day: 'numeric' });
  if (!showtime) return label;
  return `${label} · ${new Date(`2000-01-01T${showtime}`).toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' })}`;
}

/** Adapts a scheduled night to the search-result shape the schedule sheet edits. */
function nightResult(night: MovieNightView): PosterSearchResult {
  const { movie } = night;
  return { key: `night-${night.id}`, title: movie.title, year: movie.year, poster_url: movie.poster_url, sources: [movie.source], movie_id: movie.id, tmdb_id: null, include_in_rotation: movie.include_in_rotation };
}

/** Single admin view: what is scheduled, and one search to schedule or add posters. */
export function Home({ notify }: { notify: Notify }) {
  const [nights, setNights] = useState<MovieNightView[] | null>(null);
  const [confirmingId, setConfirmingId] = useState<number | null>(null);
  const [query, setQuery] = useState('');
  const debouncedQuery = useDebounced(query.trim(), 150);
  const [search, setSearch] = useState<PosterSearch | null>(null);
  const [loading, setLoading] = useState(false);
  const [pending, setPending] = useState<Set<string>>(new Set());
  const [scheduling, setScheduling] = useState<{ result: PosterSearchResult; night?: MovieNightView } | null>(null);
  const [slideshow, setSlideshow] = useState<SlideshowView | null>(null);
  const [showAll, setShowAll] = useState(false);
  const searchInput = useRef<HTMLInputElement>(null);

  const loadNights = useCallback(async () => {
    try { setNights(await api<MovieNightView[]>('/api/movie-nights')); }
    catch (caught) { notify(errorMessage(caught, 'Could not load movie nights.'), 'error'); }
  }, [notify]);

  const loadSlideshow = useCallback(async () => {
    try { setSlideshow(await api<SlideshowView>(`/api/slideshow?limit=${showAll ? 1000 : 24}`)); }
    catch (caught) { notify(errorMessage(caught, 'Could not load the slideshow.'), 'error'); }
  }, [notify, showAll]);

  useEffect(() => { void loadNights(); }, [loadNights]);
  useEffect(() => { void loadSlideshow(); }, [loadSlideshow]);

  useEffect(() => {
    if (confirmingId == null) return;
    const timer = window.setTimeout(() => setConfirmingId(null), 4000);
    return () => window.clearTimeout(timer);
  }, [confirmingId]);

  useEffect(() => {
    if (!debouncedQuery) { setSearch(null); setLoading(false); return; }
    const controller = new AbortController();
    setLoading(true);
    api<PosterSearch>(`/api/posters/search?query=${encodeURIComponent(debouncedQuery)}`, { signal: controller.signal })
      .then((next) => { setSearch(next); setLoading(false); })
      .catch((caught) => {
        if (controller.signal.aborted) return;
        setLoading(false);
        notify(errorMessage(caught, 'Search failed.'), 'error');
      });
    return () => controller.abort();
  }, [debouncedQuery, notify]);

  function patch(key: string, changes: Partial<PosterSearchResult>) {
    setSearch((current) => current && { ...current, results: current.results.map((row) => row.key === key ? { ...row, ...changes } : row) });
  }

  function setBusy(key: string, busy: boolean) {
    setPending((keys) => { const next = new Set(keys); if (busy) next.add(key); else next.delete(key); return next; });
  }

  /** Returns the saved presentation id, snapshotting a TMDB result first when needed. */
  async function ensureMovie(result: PosterSearchResult, includeInRotation: boolean) {
    if (result.movie_id != null) return result.movie_id;
    if (result.tmdb_id == null) throw new Error('This movie cannot be saved.');
    const movie = await api<MovieDetail>('/api/tmdb/import', { method: 'POST', body: jsonBody({ tmdb_id: result.tmdb_id }) });
    if (movie.include_in_rotation !== includeInRotation) {
      await api(`/api/movies/${movie.id}`, { method: 'PATCH', body: jsonBody({ include_in_rotation: includeInRotation }) });
    }
    patch(result.key, { movie_id: movie.id, include_in_rotation: includeInRotation, poster_url: movie.poster_url ?? result.poster_url });
    return movie.id;
  }

  async function toggleSlideshow(result: PosterSearchResult) {
    setBusy(result.key, true);
    try {
      if (result.movie_id == null) {
        await ensureMovie(result, true);
        notify(`${result.title} added to the slideshow.`);
      } else {
        const include = !result.include_in_rotation;
        await api(`/api/movies/${result.movie_id}`, { method: 'PATCH', body: jsonBody({ include_in_rotation: include }) });
        patch(result.key, { include_in_rotation: include });
        if (include) notify(`${result.title} added to the slideshow.`);
        else notify(`${result.title} removed from the slideshow.`, 'success', { label: 'Undo', run: () => void setInSlideshow({ id: result.movie_id!, title: result.title }, true) });
      }
      void loadSlideshow();
    } catch (caught) {
      notify(errorMessage(caught, 'Could not update the slideshow.'), 'error');
    } finally {
      setBusy(result.key, false);
    }
  }

  /** Sets a local movie's slideshow flag from anywhere on the page, keeping search cards in sync. */
  async function setInSlideshow(movie: Pick<MovieSummary, 'id' | 'title'>, include: boolean) {
    setSearch((current) => current && { ...current, results: current.results.map((row) => row.movie_id === movie.id ? { ...row, include_in_rotation: include } : row) });
    if (!include) setSlideshow((current) => current && { ...current, total: current.total - 1, items: current.items.filter((item) => item.id !== movie.id) });
    try {
      await api(`/api/movies/${movie.id}`, { method: 'PATCH', body: jsonBody({ include_in_rotation: include }) });
      if (include) notify(`${movie.title} is back in the slideshow.`);
      else notify(`${movie.title} removed from the slideshow.`, 'success', { label: 'Undo', run: () => void setInSlideshow(movie, true) });
    } catch (caught) {
      notify(errorMessage(caught, 'Could not update the slideshow.'), 'error');
    } finally {
      void loadSlideshow();
    }
  }

  function focusSearch() {
    searchInput.current?.focus();
    searchInput.current?.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }

  async function schedule(result: PosterSearchResult, eventDate: string, showtime: string | null, night?: MovieNightView) {
    if (night) {
      await api(`/api/movie-nights/${night.id}`, { method: 'PATCH', body: jsonBody({ movie_id: night.movie.id, event_date: eventDate, showtime }) });
      notify(`${result.title} moved to ${dateLabel(eventDate, showtime)}.`);
    } else {
      // Scheduling snapshots the TMDB presentation, but only + adds it to the slideshow.
      const movieId = await ensureMovie(result, false);
      await api('/api/movie-nights', { method: 'POST', body: jsonBody({ movie_id: movieId, event_date: eventDate, showtime }) });
      notify(`${result.title} scheduled for ${dateLabel(eventDate, showtime)}.`);
    }
    await loadNights();
  }

  async function removeNight(night: MovieNightView) {
    if (confirmingId !== night.id) { setConfirmingId(night.id); return; }
    setConfirmingId(null);
    try {
      await api(`/api/movie-nights/${night.id}`, { method: 'DELETE' });
      setNights((rows) => rows?.filter((row) => row.id !== night.id) ?? rows);
      notify('Movie night removed.');
    } catch (caught) {
      notify(errorMessage(caught, 'Could not remove movie night.'), 'error');
    }
  }

  const upcoming = nights?.filter((night) => !night.archived) ?? [];
  const nightByMovie = new Map(upcoming.map((night) => [night.movie.id, night]));
  const results = search?.results ?? [];
  const stale = loading || debouncedQuery !== query.trim();

  return (
    <div className="tab-body">
      <section className="section">
        <h1 className="section-title">Up next</h1>
        {nights == null && <p className="muted">Loading…</p>}
        {nights != null && upcoming.length === 0 && (
          <p className="empty-state compact">Nothing scheduled, so the TV shows your slideshow. Search for a movie below to plan a movie night.</p>
        )}
        {upcoming.length > 0 && (
          <div className="up-next">
            {upcoming.map((night, index) => {
              const confirming = confirmingId === night.id;
              const actions = (
                <div className="night-actions">
                  <button type="button" className="schedule-button" onClick={() => setScheduling({ result: nightResult(night), night })}>
                    <svg viewBox="0 0 16 16" aria-hidden="true"><rect x="2.5" y="3.5" width="11" height="10" rx="1.5" /><path d="M2.5 6.5h11M5.5 2v3M10.5 2v3" /></svg>
                    Reschedule
                  </button>
                  <button
                    type="button"
                    className={`button quiet small ${confirming ? 'danger' : ''}`}
                    aria-label={confirming ? `Confirm removing ${night.movie.title}` : `Remove ${night.movie.title}`}
                    onClick={() => void removeNight(night)}
                  >{confirming ? 'Confirm' : 'Remove'}</button>
                </div>
              );
              if (index === 0) {
                const relative = relativeDay(night.event_date);
                return (
                  <article className="next-night" key={night.id}>
                    {night.movie.poster_url && <img className="next-night-backdrop" src={night.movie.poster_url} alt="" aria-hidden="true" />}
                    <div className="next-night-poster">
                      {night.movie.poster_url ? <img src={night.movie.poster_url} alt="" /> : <span>{night.movie.title}</span>}
                    </div>
                    <div className="next-night-body">
                      <p className="eyebrow">Next movie night{relative && <> · <span className="next-night-relative">{relative}</span></>}</p>
                      <h2>{night.movie.title}</h2>
                      <p className="next-night-date">{longDateLabel(night.event_date, night.showtime)}{night.movie.year && <small> · {night.movie.year}</small>}</p>
                      {actions}
                    </div>
                  </article>
                );
              }
              return (
                <article className="later-night" key={night.id}>
                  <PosterThumb url={night.movie.poster_url} />
                  <div className="grow"><strong>{night.movie.title}</strong><small>{dateLabel(night.event_date, night.showtime)}</small></div>
                  {actions}
                </article>
              );
            })}
          </div>
        )}
      </section>

      <section className="section">
        <div className="section-head">
          <h2 className="section-title">Slideshow</h2>
          {slideshow && slideshow.total > 0 && (
            <a className="button quiet small" href="/display?preview=slideshow" target="_blank" rel="noreferrer">Preview <span aria-hidden="true">↗</span></a>
          )}
        </div>
        {slideshow == null && <p className="muted">Loading…</p>}
        {slideshow?.total === 0 && (
          <p className="empty-state compact">No posters in the slideshow yet. <button type="button" className="inline-link" onClick={focusSearch}>Find a movie</button> and tap + on its poster.</p>
        )}
        {slideshow != null && slideshow.total > 0 && (
          <>
            <p className="hint">
              Shown on the TV when nothing is playing and no movie night is scheduled. {slideshow.total} poster{slideshow.total === 1 ? '' : 's'}, a new one every {intervalLabel(slideshow.interval_seconds)}.
              {upcoming.length > 0 && <> <strong className="hint-strong">On hold until after movie night.</strong></>}
            </p>
            <div className={`slideshow-strip ${showAll ? 'expanded' : ''}`} aria-label="Posters in the slideshow">
              <button type="button" className="strip-item strip-tile" onClick={focusSearch}><span aria-hidden="true">+</span>Add</button>
              {slideshow.items.map((movie) => (
                <figure className="strip-item" key={movie.id} title={movie.title}>
                  {movie.poster_url ? <img src={movie.poster_url} alt={movie.title} loading="lazy" /> : <span>{movie.title}</span>}
                  <button type="button" className="strip-remove" aria-label={`Remove ${movie.title} from the slideshow`} onClick={() => void setInSlideshow(movie, false)}>
                    <svg viewBox="0 0 12 12" aria-hidden="true"><path d="M3 3l6 6M9 3l-6 6" /></svg>
                  </button>
                </figure>
              ))}
              {slideshow.total > slideshow.items.length && (
                <button type="button" className="strip-item strip-tile" onClick={() => setShowAll(true)}><span>+{slideshow.total - slideshow.items.length}</span>Show all</button>
              )}
              {showAll && slideshow.total > 24 && (
                <button type="button" className="strip-item strip-tile" onClick={() => setShowAll(false)}><span aria-hidden="true">−</span>Fewer</button>
              )}
            </div>
          </>
        )}
      </section>

      <section className="section">
        <h2 className="section-title">Find a movie</h2>
        <div className="poster-search">
          <svg className="poster-search-icon" viewBox="0 0 20 20" aria-hidden="true"><circle cx="8.5" cy="8.5" r="5.5" /><path d="m13 13 4 4" /></svg>
          <input
            ref={searchInput}
            type="search"
            aria-label="Search TMDB"
            placeholder="Search TMDB"
            autoComplete="off"
            autoCorrect="off"
            spellCheck={false}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
          {stale && query.trim()
            ? <span className="spinner" role="status" aria-label="Searching" />
            : query && <button type="button" className="search-clear" aria-label="Clear search" onClick={() => setQuery('')}>×</button>}
        </div>

        {search && TMDB_NOTES[search.tmdb] && <p className="hint">{TMDB_NOTES[search.tmdb]}</p>}
        {query.trim() && search && !stale && results.length === 0 && (
          <p className="empty-state">No movies found for “{search.query}”.</p>
        )}

        {results.length > 0 && (
          <div className={`poster-grid ${stale ? 'is-stale' : ''}`}>
            {results.map((result) => {
              const busy = pending.has(result.key);
              const inSlideshow = result.movie_id != null && result.include_in_rotation;
              const night = result.movie_id != null ? nightByMovie.get(result.movie_id) : undefined;
              const meta = [result.year, result.sources.map((source) => SOURCE_LABELS[source]).join(' + ')].filter(Boolean).join(' · ');
              return (
                <article className="poster-card" key={result.key}>
                  <div className="poster-card-art">
                    {result.poster_url ? <img src={result.poster_url} alt="" loading="lazy" /> : <span>{result.title}</span>}
                    {night && <span className="poster-badge">{dateLabel(night.event_date, night.showtime)}</span>}
                    <button
                      className={`slideshow-toggle ${inSlideshow ? 'on' : ''}`}
                      aria-pressed={inSlideshow}
                      aria-label={inSlideshow ? `Remove ${result.title} from the slideshow` : `Add ${result.title} to the slideshow`}
                      title={inSlideshow ? 'In the slideshow. Tap to remove.' : 'Add to the slideshow'}
                      disabled={busy}
                      onClick={() => void toggleSlideshow(result)}
                    >
                      {busy ? <span className="spinner small" /> : inSlideshow
                        ? <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M3.5 8.5l3 3 6-7" /></svg>
                        : <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M8 3v10M3 8h10" /></svg>}
                    </button>
                  </div>
                  <div className="poster-card-body">
                    <strong title={result.title}>{result.title}</strong>
                    <small title={meta}>{meta}</small>
                    <button className="schedule-button" disabled={busy} onClick={() => setScheduling({ result, night })}>
                      <svg viewBox="0 0 16 16" aria-hidden="true"><rect x="2.5" y="3.5" width="11" height="10" rx="1.5" /><path d="M2.5 6.5h11M5.5 2v3M10.5 2v3" /></svg>
                      {night ? 'Reschedule' : 'Schedule'}
                    </button>
                  </div>
                </article>
              );
            })}
          </div>
        )}

        <UploadPoster notify={notify} onUploaded={() => void loadSlideshow()} />
        {search?.tmdb === 'ok' && <p className="credit">This product uses the TMDB API but is not endorsed or certified by TMDB.</p>}
      </section>

      {scheduling && (
        <ScheduleSheet
          result={scheduling.result}
          night={scheduling.night}
          defaultDate={nextFreeFriday(new Set(upcoming.map((night) => night.event_date)))}
          onSubmit={(eventDate, showtime) => schedule(scheduling.result, eventDate, showtime, scheduling.night)}
          onClose={() => setScheduling(null)}
        />
      )}
    </div>
  );
}

function ScheduleSheet({ result, night, defaultDate, onSubmit, onClose }: {
  result: PosterSearchResult;
  night?: MovieNightView;
  defaultDate: string;
  onSubmit: (eventDate: string, showtime: string | null) => Promise<void>;
  onClose: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [eventDate, setEventDate] = useState(night?.event_date ?? defaultDate);
  const [showtime, setShowtime] = useState(night?.showtime?.slice(0, 5) ?? '');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const today = isoDate(new Date());

  useEffect(() => {
    const node = dialog.current;
    if (node && !node.open) node.showModal();
  }, []);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError('');
    try {
      await onSubmit(eventDate, showtime || null);
      dialog.current?.close();
    } catch (caught) {
      // The sheet sits above the toast layer, so show failures inside it.
      setError(errorMessage(caught, 'Could not schedule movie night.'));
      setSaving(false);
    }
  }

  return (
    <dialog
      ref={dialog}
      className="sheet"
      aria-labelledby="schedule-title"
      onClose={onClose}
      onClick={(event) => { if (event.target === dialog.current) dialog.current?.close(); }}
    >
      <form onSubmit={submit} className="form-stack">
        <div className="sheet-head">
          <PosterThumb url={result.poster_url} />
          <div className="grow">
            <p className="eyebrow">{night ? 'Reschedule movie night' : 'Schedule movie night'}</p>
            <h2 id="schedule-title">{result.title}</h2>
            {result.year && <small>{result.year}</small>}
          </div>
        </div>
        <div className="field-row">
          <label>Date<input type="date" min={today} value={eventDate} onChange={(event) => setEventDate(event.target.value)} required /></label>
          <label><span>Showtime <span className="optional">optional</span></span><input type="time" value={showtime} onChange={(event) => setShowtime(event.target.value)} /></label>
        </div>
        <div className="chip-row">
          <button type="button" className={`chip ${eventDate === today ? 'active' : ''}`} onClick={() => setEventDate(today)}>Tonight</button>
          <button type="button" className={`chip ${eventDate === defaultDate ? 'active' : ''}`} onClick={() => setEventDate(defaultDate)}>{dateLabel(defaultDate, null)}</button>
        </div>
        {error && <p className="sheet-error" role="alert">{error}</p>}
        <div className="sheet-actions">
          <button type="button" className="button quiet" onClick={() => dialog.current?.close()}>Cancel</button>
          <button className="button primary" disabled={saving}>{saving ? 'Saving…' : night ? 'Move' : 'Schedule'}</button>
        </div>
      </form>
    </dialog>
  );
}

function UploadPoster({ notify, onUploaded }: { notify: Notify; onUploaded: () => void }) {
  const [busy, setBusy] = useState(false);

  async function upload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    setBusy(true);
    try {
      await api('/api/movies/manual', { method: 'POST', body: new FormData(form) });
      form.reset();
      notify('Poster uploaded and added to the slideshow.');
      onUploaded();
    } catch (caught) {
      notify(errorMessage(caught, 'Could not upload poster.'), 'error');
    } finally {
      setBusy(false);
    }
  }

  return (
    <details className="card upload-card">
      <summary>Can’t find it? Upload your own poster</summary>
      <form onSubmit={upload} className="form-stack">
        <div className="field-row">
          <label>Title<input name="title" required maxLength={300} autoComplete="off" /></label>
          <label><span>Year <span className="optional">optional</span></span><input name="year" type="number" inputMode="numeric" min="1888" max="2200" /></label>
        </div>
        <label>Poster image<input name="poster" type="file" accept="image/jpeg,image/png,image/webp" required /></label>
        <button className="button primary" disabled={busy}>{busy ? 'Uploading…' : 'Upload poster'}</button>
      </form>
    </details>
  );
}
