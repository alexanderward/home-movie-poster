import { type FormEvent, useEffect, useRef, useState } from 'react';
import { api } from '../api';
import type { CollectionDetail, CollectionList, CollectionSummary, MovieSummary } from '../contracts.generated';
import { errorMessage, type Notify } from './shared';

function intervalLabel(seconds: number) {
  if (seconds < 60) return `${seconds} seconds`;
  const minutes = seconds / 60;
  if (minutes === 1) return 'minute';
  return Number.isInteger(minutes) ? `${minutes} minutes` : `${seconds} seconds`;
}

const plural = (count: number, word: string) => `${count} ${word}${count === 1 ? '' : 's'}`;

/** Collections: pick one to view and edit, choose which one the TV shows, and upload images to it. */
export function CollectionsSection({
  notify, collections, selected, detail, showAll, holding,
  onSelect, onShowAll, onActivate, onCreate, onEdit, onDelete, onRemoveItem, onFindMovie, onUploaded, pinnedId, onPin,
}: {
  notify: Notify;
  collections: CollectionList | null;
  selected: CollectionSummary | null;
  detail: CollectionDetail | null;
  showAll: boolean;
  /** A scheduled movie night currently takes over the TV instead of the slideshow. */
  holding: boolean;
  onSelect: (id: number) => void;
  onShowAll: (showAll: boolean) => void;
  onActivate: (id: number | null) => Promise<void>;
  onCreate: (name: string) => Promise<void>;
  onEdit: (collection: CollectionSummary, changes: CollectionEdit) => Promise<void>;
  onDelete: (collection: CollectionSummary) => Promise<void>;
  onRemoveItem: (movie: Pick<MovieSummary, 'id' | 'title'>) => void;
  onFindMovie: () => void;
  onUploaded: () => void;
  /** The image pinned to the TV by a poster override, if any. */
  pinnedId: number | null;
  /** Pins an image to the TV, or unpins it when it's already pinned. */
  onPin: (movie: Pick<MovieSummary, 'id' | 'title'>) => void;
}) {
  const [sheet, setSheet] = useState<{ mode: 'create' } | { mode: 'edit'; collection: CollectionSummary } | null>(null);
  const [confirmingDelete, setConfirmingDelete] = useState<number | null>(null);

  useEffect(() => {
    if (confirmingDelete == null) return;
    const timer = window.setTimeout(() => setConfirmingDelete(null), 4000);
    return () => window.clearTimeout(timer);
  }, [confirmingDelete]);

  async function remove(collection: CollectionSummary) {
    if (confirmingDelete !== collection.id) { setConfirmingDelete(collection.id); return; }
    setConfirmingDelete(null);
    await onDelete(collection);
  }

  const items = collections?.items ?? [];
  const active = items.find((row) => row.active) ?? null;
  // Ignore a detail response for a previously selected collection while the new one loads.
  const current = detail && selected && detail.id === selected.id ? detail : null;

  return (
    <section className="section">
      <div className="section-head">
        <h2 className="section-title">Collections</h2>
        {active && active.item_count > 0 && (
          <a className="button quiet small" href="/display?preview=slideshow" target="_blank" rel="noreferrer">Preview <span aria-hidden="true">↗</span></a>
        )}
      </div>

      {collections == null && <p className="muted">Loading…</p>}
      {collections != null && items.length === 0 && (
        <p className="empty-state compact">
          Collections group what the TV rotates through when it’s idle: movie posters, artwork, family photos.{' '}
          <button type="button" className="inline-link" onClick={() => setSheet({ mode: 'create' })}>Create your first collection</button>
        </p>
      )}

      {items.length > 0 && (
        <div className="collection-tabs" role="tablist" aria-label="Collections">
          {items.map((row) => (
            <button
              key={row.id}
              type="button"
              role="tab"
              aria-selected={row.id === selected?.id}
              className={`collection-tab ${row.id === selected?.id ? 'selected' : ''}`}
              onClick={() => onSelect(row.id)}
            >
              {row.active && <i className="on-tv-dot" title="On the TV" aria-label="On the TV" />}
              <span>{row.name}</span>
              <small>{row.item_count}</small>
            </button>
          ))}
          <button type="button" className="collection-tab add" onClick={() => setSheet({ mode: 'create' })}>
            <span aria-hidden="true">+</span> New
          </button>
        </div>
      )}

      {selected && (
        <>
          <div className="collection-status">
            <p className="hint">
              {selected.active ? (
                <>
                  On the TV when nothing is playing and no movie night is scheduled. {plural(selected.item_count, 'image')}, a new one every {intervalLabel(collections?.interval_seconds ?? 60)}.
                  {holding && <> <strong className="hint-strong">On hold until after movie night.</strong></>}
                </>
              ) : (
                <>Not on the TV. {active ? <>The TV is showing <strong className="hint-strong">{active.name}</strong>.</> : 'No collection is on the TV.'}</>
              )}
            </p>
            <div className="collection-actions">
              {selected.active
                ? <button type="button" className="button quiet small" onClick={() => void onActivate(null)}>Take off TV</button>
                : <button type="button" className="button primary small" onClick={() => void onActivate(selected.id)}>Show on TV</button>}
              <button type="button" className="button quiet small" onClick={() => setSheet({ mode: 'edit', collection: selected })}>Edit</button>
              <button
                type="button"
                className={`button quiet small ${confirmingDelete === selected.id ? 'danger' : ''}`}
                aria-label={confirmingDelete === selected.id ? `Confirm deleting ${selected.name}` : `Delete ${selected.name}`}
                onClick={() => void remove(selected)}
              >{confirmingDelete === selected.id ? 'Confirm delete' : 'Delete'}</button>
            </div>
          </div>

          {current == null && <p className="muted">Loading…</p>}
          {current?.item_count === 0 && (
            <p className="empty-state compact">
              Nothing in {current.name} yet. <button type="button" className="inline-link" onClick={onFindMovie}>Find a movie</button> and tap + on its poster, or upload images below.
            </p>
          )}
          {current != null && current.item_count > 0 && (
            <div className={`slideshow-strip ${showAll ? 'expanded' : ''}`} aria-label={`Images in ${current.name}`}>
              <button type="button" className="strip-item strip-tile" onClick={onFindMovie}><span aria-hidden="true">+</span>Add</button>
              {current.items.map((movie) => (
                <figure className={`strip-item ${pinnedId === movie.id ? 'pinned' : ''}`} key={movie.id} title={movie.title}>
                  {movie.poster_url ? <img src={movie.poster_url} alt={movie.title} loading="lazy" /> : <span>{movie.title}</span>}
                  {movie.poster_url && (
                    <button
                      type="button"
                      className="strip-pin"
                      aria-pressed={pinnedId === movie.id}
                      aria-label={pinnedId === movie.id ? `Unpin ${movie.title} from the TV` : `Pin ${movie.title} to the TV`}
                      onClick={() => onPin(movie)}
                    >
                      <svg viewBox="0 0 12 12" aria-hidden="true"><path d="M4.5 1.5h3l-.5 3 2 1.5v1h-6v-1l2-1.5zM6 7v3.5" /></svg>
                    </button>
                  )}
                  <button type="button" className="strip-remove" aria-label={`Remove ${movie.title} from ${current.name}`} onClick={() => onRemoveItem(movie)}>
                    <svg viewBox="0 0 12 12" aria-hidden="true"><path d="M3 3l6 6M9 3l-6 6" /></svg>
                  </button>
                </figure>
              ))}
              {current.item_count > current.items.length && (
                <button type="button" className="strip-item strip-tile" onClick={() => onShowAll(true)}><span>+{current.item_count - current.items.length}</span>Show all</button>
              )}
              {showAll && current.item_count > 24 && (
                <button type="button" className="strip-item strip-tile" onClick={() => onShowAll(false)}><span aria-hidden="true">−</span>Fewer</button>
              )}
            </div>
          )}

          <UploadImages collection={selected} notify={notify} onUploaded={onUploaded} />
        </>
      )}

      {sheet && (
        <CollectionSheet
          collection={sheet.mode === 'edit' ? sheet.collection : null}
          onSubmit={(changes) => sheet.mode === 'create' ? onCreate(changes.name) : onEdit(sheet.collection, changes)}
          onClose={() => setSheet(null)}
        />
      )}
    </section>
  );
}

export type CollectionEdit = { name: string; tv_headline: string; show_headline: boolean };

/** Create a collection (name only), or edit one: its name and what the TV's top band says during its slideshow. */
function CollectionSheet({ collection, onSubmit, onClose }: {
  collection: CollectionSummary | null;
  onSubmit: (changes: CollectionEdit) => Promise<void>;
  onClose: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [name, setName] = useState(collection?.name ?? '');
  const [headline, setHeadline] = useState(collection?.tv_headline ?? '');
  const [showHeadline, setShowHeadline] = useState(collection?.show_headline ?? true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    const node = dialog.current;
    if (node && !node.open) node.showModal();
  }, []);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError('');
    try {
      await onSubmit({ name: name.trim(), tv_headline: headline.trim(), show_headline: showHeadline });
      dialog.current?.close();
    } catch (caught) {
      setError(errorMessage(caught, 'Could not save the collection.'));
      setSaving(false);
    }
  }

  return (
    <dialog
      ref={dialog}
      className="sheet"
      aria-labelledby="collection-sheet-title"
      onClose={onClose}
      onClick={(event) => { if (event.target === dialog.current) dialog.current?.close(); }}
    >
      <form onSubmit={submit} className="form-stack">
        <h2 id="collection-sheet-title" className="sheet-title">{collection ? 'Edit collection' : 'New collection'}</h2>
        <label>Name<input value={name} onChange={(event) => setName(event.target.value)} required maxLength={120} autoComplete="off" autoFocus placeholder="Artwork, Holidays, Sci-fi…" /></label>
        {collection && (
          <fieldset className="form-stack headline-fields">
            <legend>TV headline</legend>
            <label className="check-row">
              <input type="checkbox" checked={showHeadline} onChange={(event) => setShowHeadline(event.target.checked)} />
              <span>Show a headline above the poster</span>
            </label>
            {showHeadline && (
              <label>
                <span>Headline <span className="optional">optional</span></span>
                <input value={headline} onChange={(event) => setHeadline(event.target.value)} maxLength={40} autoComplete="off" placeholder={name.trim() || 'Collection name'} />
              </label>
            )}
            <p className="hint">{showHeadline
              ? 'Shown in capitals across the top of the TV during this slideshow. Leave blank to use the name. Try “Now Showing” or “Coming Attractions”.'
              : 'The top of the TV stays black so the poster stands alone.'}</p>
          </fieldset>
        )}
        {error && <p className="sheet-error" role="alert">{error}</p>}
        <div className="sheet-actions">
          <button type="button" className="button quiet" onClick={() => dialog.current?.close()}>Cancel</button>
          <button className="button primary" disabled={saving || !name.trim()}>{saving ? 'Saving…' : collection ? 'Save' : 'Create'}</button>
        </div>
      </form>
    </dialog>
  );
}

/** "summer-trip_04.jpg" -> "summer trip 04" */
function titleFromFile(file: File) {
  return file.name.replace(/\.[^.]+$/, '').replace(/[_-]+/g, ' ').trim() || 'Untitled';
}

function UploadImages({ collection, notify, onUploaded }: { collection: CollectionSummary; notify: Notify; onUploaded: () => void }) {
  const [busy, setBusy] = useState(false);
  const [count, setCount] = useState(0);

  async function upload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    const files = data.getAll('images').filter((value): value is File => value instanceof File && value.size > 0);
    const title = String(data.get('title') ?? '').trim();
    const year = String(data.get('year') ?? '').trim();
    if (files.length === 0) return;
    setBusy(true);
    let uploaded = 0;
    const failures: string[] = [];
    for (const file of files) {
      const body = new FormData();
      body.set('title', files.length === 1 && title ? title : titleFromFile(file));
      if (files.length === 1 && year) body.set('year', year);
      body.set('collection_id', String(collection.id));
      body.set('poster', file);
      try {
        await api('/api/movies/manual', { method: 'POST', body });
        uploaded += 1;
      } catch (caught) {
        failures.push(`${file.name}: ${errorMessage(caught, 'upload failed')}`);
      }
    }
    setBusy(false);
    if (uploaded) {
      form.reset();
      setCount(0);
      onUploaded();
    }
    if (failures.length) notify(`${uploaded ? `Added ${plural(uploaded, 'image')}. ` : ''}Could not upload ${failures.join('; ')}`, 'error');
    else notify(`Added ${plural(uploaded, 'image')} to ${collection.name}.`);
  }

  return (
    <details className="card upload-card">
      <summary>Upload images to {collection.name}</summary>
      <form onSubmit={upload} className="form-stack">
        <label>Images<input name="images" type="file" accept="image/jpeg,image/png,image/webp" multiple required onChange={(event) => setCount(event.target.files?.length ?? 0)} /></label>
        {count > 1
          ? <p className="hint">Each image is titled from its file name.</p>
          : (
            <div className="field-row">
              <label><span>Title <span className="optional">optional</span></span><input name="title" maxLength={300} autoComplete="off" placeholder="From file name" /></label>
              <label><span>Year <span className="optional">optional</span></span><input name="year" type="number" inputMode="numeric" min="1" max="2200" /></label>
            </div>
          )}
        <button className="button primary" disabled={busy}>{busy ? 'Uploading…' : count > 1 ? `Upload ${count} images` : 'Upload'}</button>
      </form>
    </details>
  );
}
