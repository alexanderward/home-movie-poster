import { type FormEvent, useCallback, useEffect, useRef, useState } from 'react';
import { api, jsonBody } from '../api';
import type { CollectionDetail, CollectionList, CollectionSummary, DisplayOverrideInput, DisplayOverrideView, MovieDetail, MovieNightView, MovieSummary, PosterSearch, PosterSearchResult } from '../contracts.generated';
import { type CollectionEdit, CollectionsSection } from './Collections';
import { OnTvSection, type OverrideChoice } from './OnTv';
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
  return { key: `night-${night.id}`, title: movie.title, year: movie.year, poster_url: movie.poster_url, sources: [movie.source], movie_id: movie.id, tmdb_id: null, collection_ids: movie.collection_ids };
}

/** Single admin view: what is scheduled, the collections the TV rotates through, and one search. */
export function Home({ notify }: { notify: Notify }) {
  const [nights, setNights] = useState<MovieNightView[] | null>(null);
  const [confirmingId, setConfirmingId] = useState<number | null>(null);
  const [query, setQuery] = useState('');
  const debouncedQuery = useDebounced(query.trim(), 150);
  const [search, setSearch] = useState<PosterSearch | null>(null);
  const [loading, setLoading] = useState(false);
  const [pending, setPending] = useState<Set<string>>(new Set());
  const [scheduling, setScheduling] = useState<{ result: PosterSearchResult; night?: MovieNightView } | null>(null);
  const [collections, setCollections] = useState<CollectionList | null>(null);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [detail, setDetail] = useState<CollectionDetail | null>(null);
  const [showAll, setShowAll] = useState(false);
  const [override, setOverride] = useState<DisplayOverrideView | null>(null);
  const [overrideUnavailable, setOverrideUnavailable] = useState(false);
  const searchInput = useRef<HTMLInputElement>(null);

  const loadNights = useCallback(async () => {
    try { setNights(await api<MovieNightView[]>('/api/movie-nights')); }
    catch (caught) { notify(errorMessage(caught, 'Could not load movie nights.'), 'error'); }
  }, [notify]);

  /** Loads every collection, keeping the selection when it still exists, else the one on the TV. */
  const loadCollections = useCallback(async (select?: number) => {
    try {
      const list = await api<CollectionList>('/api/collections');
      setCollections(list);
      setSelectedId((current) => {
        const wanted = select ?? current;
        if (wanted != null && list.items.some((row) => row.id === wanted)) return wanted;
        return list.active_id ?? list.items[0]?.id ?? null;
      });
    } catch (caught) { notify(errorMessage(caught, 'Could not load collections.'), 'error'); }
  }, [notify]);

  const loadDetail = useCallback(async () => {
    if (selectedId == null) { setDetail(null); return; }
    try { setDetail(await api<CollectionDetail>(`/api/collections/${selectedId}?limit=${showAll ? 1000 : 24}`)); }
    catch (caught) { notify(errorMessage(caught, 'Could not load the collection.'), 'error'); }
  }, [notify, selectedId, showAll]);

  const refreshCollections = useCallback(() => { void loadCollections(); void loadDetail(); }, [loadCollections, loadDetail]);

  const loadOverride = useCallback(async () => {
    try {
      setOverride(await api<DisplayOverrideView>('/api/display/override'));
      setOverrideUnavailable(false);
    } catch {
      // The next poll retries; the TV keeps running either way.
      setOverrideUnavailable(true);
    }
  }, []);

  useEffect(() => { void loadNights(); }, [loadNights]);
  // Keeps "On the TV" current as playback starts and stops and slides change.
  useEffect(() => {
    void loadOverride();
    const timer = window.setInterval(() => void loadOverride(), 5000);
    return () => window.clearInterval(timer);
  }, [loadOverride, nights, collections]);
  useEffect(() => { void loadCollections(); }, [loadCollections]);
  useEffect(() => { void loadDetail(); }, [loadDetail]);

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
  async function ensureMovie(result: PosterSearchResult) {
    if (result.movie_id != null) return result.movie_id;
    if (result.tmdb_id == null) throw new Error('This movie cannot be saved.');
    const movie = await api<MovieDetail>('/api/tmdb/import', { method: 'POST', body: jsonBody({ tmdb_id: result.tmdb_id }) });
    patch(result.key, { movie_id: movie.id, collection_ids: movie.collection_ids, poster_url: movie.poster_url ?? result.poster_url });
    return movie.id;
  }

  /** Adds a saved movie to, or removes it from, a collection, keeping search cards and the strip in sync. */
  async function setMembership(movie: Pick<MovieSummary, 'id' | 'title'>, collection: Pick<CollectionSummary, 'id' | 'name'>, include: boolean) {
    setSearch((current) => current && {
      ...current,
      results: current.results.map((row) => row.movie_id !== movie.id ? row : {
        ...row,
        collection_ids: include ? [...new Set([...row.collection_ids, collection.id])] : row.collection_ids.filter((id) => id !== collection.id),
      }),
    });
    if (!include) setDetail((current) => current && current.id === collection.id ? { ...current, item_count: current.item_count - 1, items: current.items.filter((item) => item.id !== movie.id) } : current);
    try {
      await api(`/api/collections/${collection.id}/items/${movie.id}`, { method: include ? 'PUT' : 'DELETE' });
      if (include) notify(`${movie.title} added to ${collection.name}.`);
      else notify(`${movie.title} removed from ${collection.name}.`, 'success', { label: 'Undo', run: () => void setMembership(movie, collection, true) });
    } catch (caught) {
      notify(errorMessage(caught, 'Could not update the collection.'), 'error');
    } finally {
      refreshCollections();
    }
  }

  async function toggleInCollection(result: PosterSearchResult, collection: CollectionSummary) {
    setBusy(result.key, true);
    try {
      const movieId = await ensureMovie(result);
      await setMembership({ id: movieId, title: result.title }, collection, !result.collection_ids.includes(collection.id));
    } catch (caught) {
      notify(errorMessage(caught, 'Could not update the collection.'), 'error');
    } finally {
      setBusy(result.key, false);
    }
  }

  async function activate(id: number | null) {
    try {
      const list = await api<CollectionList>('/api/collections/active', { method: 'PUT', body: jsonBody({ collection_id: id }) });
      setCollections(list);
      const name = list.items.find((row) => row.id === id)?.name;
      notify(name ? `${name} is now on the TV.` : 'No collection is on the TV.');
    } catch (caught) {
      notify(errorMessage(caught, 'Could not change what the TV shows.'), 'error');
    }
  }

  async function changeOverride(input: OverrideChoice) {
    const payload: DisplayOverrideInput = { collection_id: null, movie_id: null, ...input };
    try {
      const next = await api<DisplayOverrideView>('/api/display/override', { method: 'PUT', body: jsonBody(payload) });
      setOverride(next);
      if (input.mode === 'auto') notify('The TV is back to automatic.');
      else if (input.mode === 'poster') notify(`${next.movie?.title ?? 'That poster'} is pinned to the TV.`);
      else notify(`The TV is showing the ${input.mode === 'movie_night' ? 'movie night' : 'slideshow'} until you switch back.`);
    } catch (caught) {
      notify(errorMessage(caught, 'Could not change what the TV shows.'), 'error');
    }
  }

  async function createCollection(name: string) {
    const created = await api<CollectionDetail>('/api/collections', { method: 'POST', body: jsonBody({ name }) });
    setShowAll(false);
    await loadCollections(created.id);
    notify(created.active ? `${created.name} created and shown on the TV.` : `${created.name} created.`);
  }

  async function editCollection(collection: CollectionSummary, changes: CollectionEdit) {
    await api(`/api/collections/${collection.id}`, { method: 'PATCH', body: jsonBody(changes) });
    refreshCollections();
    notify(changes.name !== collection.name ? `Renamed to ${changes.name}.` : `Saved ${changes.name}.`);
  }

  async function deleteCollection(collection: CollectionSummary) {
    try {
      await api(`/api/collections/${collection.id}`, { method: 'DELETE' });
      setSearch((current) => current && { ...current, results: current.results.map((row) => ({ ...row, collection_ids: row.collection_ids.filter((id) => id !== collection.id) })) });
      setSelectedId(null);
      await loadCollections();
      notify(`${collection.name} deleted. Its images stay saved for other collections.`);
    } catch (caught) {
      notify(errorMessage(caught, 'Could not delete the collection.'), 'error');
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
      // Scheduling snapshots the TMDB presentation, but only + adds it to a collection.
      const movieId = await ensureMovie(result);
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
  const selected = collections?.items.find((row) => row.id === selectedId) ?? null;

  return (
    <div className="tab-body">
      <OnTvSection override={override} unavailable={overrideUnavailable} collections={collections} hasMovieNight={upcoming.length > 0} onChange={changeOverride} />

      <section className="section">
        <h2 className="section-title">Up next</h2>
        {nights == null && <p className="muted">Loading…</p>}
        {nights != null && upcoming.length === 0 && (
          <p className="empty-state compact">Nothing scheduled, so the TV shows your collection. Search for a movie below to plan a movie night.</p>
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

      <CollectionsSection
        notify={notify}
        collections={collections}
        selected={selected}
        detail={detail}
        showAll={showAll}
        holding={upcoming.length > 0}
        onSelect={(id) => { setSelectedId(id); setShowAll(false); }}
        onShowAll={setShowAll}
        onActivate={activate}
        onCreate={createCollection}
        onEdit={editCollection}
        onDelete={deleteCollection}
        onRemoveItem={(movie) => { if (selected) void setMembership(movie, selected, false); }}
        pinnedId={override?.mode === 'poster' ? override.movie?.id ?? null : null}
        onPin={(movie) => void changeOverride(override?.mode === 'poster' && override.movie?.id === movie.id ? { mode: 'auto' } : { mode: 'poster', movie_id: movie.id })}
        onFindMovie={focusSearch}
        onUploaded={refreshCollections}
      />

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
              const inCollection = selected != null && result.collection_ids.includes(selected.id);
              const night = result.movie_id != null ? nightByMovie.get(result.movie_id) : undefined;
              const meta = [result.year, result.sources.map((source) => SOURCE_LABELS[source]).join(' + ')].filter(Boolean).join(' · ');
              return (
                <article className="poster-card" key={result.key}>
                  <div className="poster-card-art">
                    {result.poster_url ? <img src={result.poster_url} alt="" loading="lazy" /> : <span>{result.title}</span>}
                    {night && <span className="poster-badge">{dateLabel(night.event_date, night.showtime)}</span>}
                    {selected && (
                      <button
                        className={`slideshow-toggle ${inCollection ? 'on' : ''}`}
                        aria-pressed={inCollection}
                        aria-label={inCollection ? `Remove ${result.title} from ${selected.name}` : `Add ${result.title} to ${selected.name}`}
                        title={inCollection ? `In ${selected.name}. Tap to remove.` : `Add to ${selected.name}`}
                        disabled={busy}
                        onClick={() => void toggleInCollection(result, selected)}
                      >
                        {busy ? <span className="spinner small" /> : inCollection
                          ? <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M3.5 8.5l3 3 6-7" /></svg>
                          : <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M8 3v10M3 8h10" /></svg>}
                      </button>
                    )}
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
