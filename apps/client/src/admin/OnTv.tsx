import type { CollectionList, DisplayOverrideInput, DisplayOverrideView } from '../contracts.generated';
import { PosterThumb } from './shared';

type Mode = DisplayOverrideInput['mode'];
/** An override to apply; ids that don't apply to the mode may be left out. */
export type OverrideChoice = Pick<DisplayOverrideInput, 'mode'> & Partial<DisplayOverrideInput>;

const MODES: Array<{ mode: Mode; label: string }> = [
  { mode: 'auto', label: 'Automatic' },
  { mode: 'movie_night', label: 'Movie night' },
  { mode: 'slideshow', label: 'Slideshow' },
  { mode: 'poster', label: 'Poster' },
];

const NOW_LABELS: Record<DisplayOverrideView['now']['mode'], string> = {
  now_playing: 'Now playing',
  scheduled: 'Movie night',
  rotation: 'Slideshow',
  pinned: 'Pinned poster',
  setup: 'Setup screen',
};

/**
 * Forces what the TV shows (a movie night, a slideshow, or one poster) until switched back to
 * automatic, and says what the TV is showing right now.
 */
export function OnTvSection({ override, unavailable, collections, hasMovieNight, onChange }: {
  override: DisplayOverrideView | null;
  /** The server didn't answer, e.g. it's still running a build from before overrides existed. */
  unavailable: boolean;
  collections: CollectionList | null;
  hasMovieNight: boolean;
  onChange: (input: OverrideChoice) => Promise<void>;
}) {
  if (override == null) {
    return (
      <section className="section">
        <h1 className="section-title">On the TV</h1>
        <p className="muted">{unavailable ? 'Can’t reach the server to see what’s on the TV. If you just updated Frame, rebuild and restart it.' : 'Loading…'}</p>
      </section>
    );
  }

  const filled = collections?.items.filter((row) => row.item_count > 0) ?? [];
  const activeName = collections?.items.find((row) => row.active)?.name;
  const available: Record<Mode, boolean> = {
    auto: true,
    movie_night: hasMovieNight,
    slideshow: filled.length > 0,
    poster: override.movie != null,
  };
  const now = override.now;
  const forcedOn = override.mode !== 'auto';

  function choose(mode: Mode) {
    if (mode === 'poster' && override?.movie) void onChange({ mode, movie_id: override.movie.id });
    else void onChange({ mode });
  }

  return (
    <section className="section">
      <div className="section-head">
        <h1 className="section-title">On the TV</h1>
        {forcedOn && <button type="button" className="button quiet small" onClick={() => void onChange({ mode: 'auto' })}>Back to automatic</button>}
      </div>

      <fieldset className="segmented override-modes" aria-label="What the TV shows">
        {MODES.map(({ mode, label }) => (
          <label key={mode} className={available[mode] || override.mode === mode ? '' : 'disabled'}>
            <input
              type="radio"
              name="display-override"
              checked={override.mode === mode}
              disabled={!available[mode] && override.mode !== mode}
              onChange={() => choose(mode)}
            />
            <span>{label}</span>
          </label>
        ))}
      </fieldset>

      {override.mode === 'slideshow' && filled.length > 0 && (
        <label className="override-collection">
          <span className="muted">Collection</span>
          <select
            value={override.collection_id ?? ''}
            onChange={(event) => void onChange({ mode: 'slideshow', collection_id: event.target.value ? Number(event.target.value) : null })}
          >
            <option value="">{activeName ? `The one on the TV (${activeName})` : 'The one on the TV'}</option>
            {filled.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
          </select>
        </label>
      )}

      <div className={`now-showing ${forcedOn ? 'forced' : ''}`}>
        <PosterThumb url={now.poster_url} />
        <div className="grow">
          <small>{NOW_LABELS[now.mode]}{now.headline && now.mode !== 'setup' ? ` · ${now.headline}` : ''}</small>
          <strong>{now.mode === 'setup' ? 'Nothing to show yet' : now.title}</strong>
        </div>
      </div>

      <p className="hint">
        {override.mode === 'auto' && 'Shows what’s playing, then the next movie night, then your collection. Pick an option to take over the TV until you switch back.'}
        {forcedOn && override.forced && <strong className="hint-strong">Override on. It stays until you switch back to automatic.</strong>}
        {forcedOn && !override.forced && <><strong className="hint-strong">Override on, but there’s nothing to show for it</strong>, so the TV is following the automatic order.</>}
        {!available.poster && <> To pin one poster, tap the pin on any image in a collection.</>}
      </p>
    </section>
  );
}
