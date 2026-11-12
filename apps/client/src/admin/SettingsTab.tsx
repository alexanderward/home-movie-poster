import { type FormEvent, type ReactNode, useEffect, useMemo, useState } from 'react';
import { api, jsonBody } from '../api';
import type {
  ApplicationSettingsInput,
  ApplicationSettingsView,
  DiscoveredDeviceView,
  PlayerSettingsInput,
} from '../contracts.generated';
import { errorMessage, type Notify } from './shared';

const timeZones: string[] =
  (Intl as unknown as { supportedValuesOf?: (key: string) => string[] }).supportedValuesOf?.('timeZone') ?? [];

function displayDraft(row: ApplicationSettingsView): ApplicationSettingsInput {
  return { rotation: row.rotation, slideshow_interval_seconds: row.slideshow_interval_seconds, timezone: row.timezone };
}

function playerDraft(row: ApplicationSettingsView): PlayerSettingsInput {
  return { player_serial: row.player_serial, manual_host: row.manual_host };
}

const same = (left: object, right: object) => JSON.stringify(left) === JSON.stringify(right);

function duration(seconds: number) {
  if (seconds < 60) return `${seconds} sec`;
  const minutes = Math.floor(seconds / 60);
  const rest = seconds % 60;
  return rest ? `${minutes} min ${rest} sec` : `${minutes} min`;
}

function SettingRow({ label, hint, htmlFor, inline, children }: { label: ReactNode; hint?: ReactNode; htmlFor?: string; inline?: boolean; children: ReactNode }) {
  return (
    <div className={`setting-row ${inline ? 'inline' : ''}`}>
      <div className="setting-text">
        {htmlFor ? <label htmlFor={htmlFor}>{label}</label> : <span className="setting-label">{label}</span>}
        {hint && <p className="hint">{hint}</p>}
      </div>
      <div className="setting-control">{children}</div>
    </div>
  );
}

function Group({ title, aside, children }: { title: string; aside?: ReactNode; children: ReactNode }) {
  return (
    <section className="settings-group">
      <header className="settings-group-head"><h2>{title}</h2>{aside}</header>
      <div className="settings-panel">{children}</div>
    </section>
  );
}

interface ServerAddress { address: string; name?: string; sameAsPlayer?: boolean }

const subnet = (ip: string) => ip.split('.').slice(0, 3).join('.');

/**
 * Addresses other devices can use to reach this server. Opened as localhost, "localhost" is useless to a TV,
 * so prefer the LAN addresses the dev server reports, with the one on the player's network first.
 */
function serverAddresses(playerIp: string | null | undefined): ServerAddress[] {
  const host = window.location.hostname;
  const loopback = host === 'localhost' || host === '[::1]' || host.startsWith('127.');
  if (!loopback || __LAN_ADDRESSES__.length === 0) return [{ address: host }];
  return __LAN_ADDRESSES__
    .map((lan) => ({ ...lan, sameAsPlayer: Boolean(playerIp && subnet(playerIp) === subnet(lan.address)) }))
    .sort((left, right) => Number(right.sameAsPlayer) - Number(left.sameAsPlayer));
}

function CopyValue({ value }: { value: string }) {
  const [copied, setCopied] = useState(false);
  const canCopy = Boolean(navigator.clipboard?.writeText);
  return (
    <span className="copy-value">
      <code className="value">{value}</code>
      {canCopy && (
        <button
          type="button"
          className="button quiet small"
          onClick={() => void navigator.clipboard.writeText(value).then(() => { setCopied(true); window.setTimeout(() => setCopied(false), 1500); })}
        >
          {copied ? 'Copied' : 'Copy'}
        </button>
      )}
    </span>
  );
}

export function SettingsTab({ notify }: { notify: Notify }) {
  const serverPort = window.location.port || (window.location.protocol === 'https:' ? '443' : '80');
  const originFor = (host: string) => `${window.location.protocol}//${host}${window.location.port ? `:${window.location.port}` : ''}`;
  const [saved, setSaved] = useState<ApplicationSettingsView | null>(null);
  const [display, setDisplay] = useState<ApplicationSettingsInput | null>(null);
  const [player, setPlayer] = useState<PlayerSettingsInput | null>(null);
  const [devices, setDevices] = useState<DiscoveredDeviceView[] | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    Promise.all([
      api<ApplicationSettingsView>('/api/settings'),
      api<DiscoveredDeviceView[]>('/api/devices'),
    ]).then(([nextSettings, nextDevices]) => {
      setSaved(nextSettings);
      setDisplay(displayDraft(nextSettings));
      setPlayer(playerDraft(nextSettings));
      setDevices(nextDevices);
    }).catch((caught) => notify(errorMessage(caught, 'Could not load settings.'), 'error'));
  }, [notify]);

  const displayDirty = useMemo(() => Boolean(saved && display && !same(displayDraft(saved), display)), [saved, display]);
  const playerDirty = useMemo(() => Boolean(saved && player && !same(playerDraft(saved), player)), [saved, player]);
  const dirty = displayDirty || playerDirty;

  async function save(event: FormEvent) {
    event.preventDefault();
    if (!dirty || !display || !player) return;
    setBusy(true);
    try {
      let next = saved;
      if (displayDirty) next = await api<ApplicationSettingsView>('/api/settings', { method: 'PUT', body: jsonBody(display) });
      if (playerDirty) next = await api<ApplicationSettingsView>('/api/devices/player', { method: 'PUT', body: jsonBody(player) });
      if (next) {
        setSaved(next);
        setDisplay(displayDraft(next));
        setPlayer(playerDraft(next));
      }
      notify('Settings saved.');
    } catch (caught) {
      notify(errorMessage(caught, 'Could not save settings.'), 'error');
    } finally {
      setBusy(false);
    }
  }

  function discard() {
    if (!saved) return;
    setDisplay(displayDraft(saved));
    setPlayer(playerDraft(saved));
  }

  if (!saved || !display || !player || !devices) {
    return <div className="tab-body settings-page"><h1 className="tab-title">Settings</h1><p className="muted">Loading...</p></div>;
  }

  const playable = devices.filter((device) => device.supports_playback);
  const active = devices.find((device) => device.selected_as_player);
  const addresses = serverAddresses(active?.ip_address);

  return (
    <form className="tab-body settings-page" onSubmit={(event) => void save(event)}>
      <h1 className="tab-title">Settings</h1>

      <Group title="Television">
        <SettingRow label="Rotation" hint="How the screen is mounted.">
          <fieldset className="segmented" aria-label="Rotation">
            {([0, 90, 270] as const).map((value) => (
              <label key={value}>
                <input type="radio" name="rotation" checked={display.rotation === value} onChange={() => setDisplay({ ...display, rotation: value })} />
                <span><i className="rotation-glyph" style={{ transform: `rotate(${value}deg)` }} aria-hidden="true" />{value}°</span>
              </label>
            ))}
          </fieldset>
        </SettingRow>
        <SettingRow label="Poster interval" hint="Time each slideshow poster stays on screen." htmlFor="interval">
          <div className="range-field">
            <input id="interval" type="range" min="10" max="300" step="5" value={display.slideshow_interval_seconds} onChange={(event) => setDisplay({ ...display, slideshow_interval_seconds: Number(event.target.value) })} />
            <output htmlFor="interval">{duration(display.slideshow_interval_seconds)}</output>
          </div>
        </SettingRow>
        <SettingRow label="Timezone" hint="Used for showtimes and the schedule." htmlFor="timezone">
          <input id="timezone" list="timezones" value={display.timezone} onChange={(event) => setDisplay({ ...display, timezone: event.target.value })} autoCapitalize="off" autoCorrect="off" spellCheck={false} />
          <datalist id="timezones">{timeZones.map((zone) => <option key={zone} value={zone} />)}</datalist>
        </SettingRow>
      </Group>

      <Group
        title="Strato player"
        aside={<span className={`status-chip ${devices.length ? 'ready' : ''}`}>{devices.length ? `${devices.length} found` : 'Searching'}</span>}
      >
        <div className="setting-row device-status">
          <span className={`connection-dot ${active ? 'online' : ''}`} aria-hidden="true" />
          <div className="grow">
            <strong>{active ? (active.friendly_name || active.serial_number) : 'No player connected'}</strong>
            <small>
              {active
                ? [active.device_type, active.ip_address].filter(Boolean).join(' · ')
                : 'Still scanning the network. On Windows, run the monitor natively or enter the address below.'}
            </small>
          </div>
        </div>
        <SettingRow label="Playback player" htmlFor="player">
          <select id="player" value={player.player_serial} onChange={(event) => setPlayer({ ...player, player_serial: event.target.value })}>
            <option value="">Auto-select</option>
            {playable.map((device) => <option value={device.serial_number} key={device.serial_number}>{device.friendly_name || device.serial_number}</option>)}
          </select>
        </SettingRow>
        <SettingRow label={<>Manual address <span className="optional">optional</span></>} hint="Use this if the player isn't found automatically." htmlFor="manual-host">
          <input id="manual-host" value={player.manual_host} onChange={(event) => setPlayer({ ...player, manual_host: event.target.value })} placeholder="192.168.5.104" inputMode="decimal" autoCapitalize="off" autoCorrect="off" spellCheck={false} />
        </SettingRow>
      </Group>
      <p className="settings-footnote">Read-only connection. Live playback takes over the TV from the schedule and slideshow. No Kaleidescape library data is imported.</p>

      <Group title="Server">
        {addresses.map((entry) => (
          <div className="setting-row network-row" key={entry.address}>
            <div className="setting-text">
              <span className="setting-label network-name">
                {entry.name ?? 'This server'}
                {entry.sameAsPlayer && <span className="status-chip ready">Strato network</span>}
              </span>
              <p className="hint"><code>{entry.address}</code></p>
            </div>
            <div className="network-links">
              <div className="link-line"><span>TV</span><CopyValue value={`${originFor(entry.address)}/display`} /></div>
              <div className="link-line"><span>Phone</span><CopyValue value={`${originFor(entry.address)}/admin`} /></div>
            </div>
          </div>
        ))}
        <SettingRow label="Web port" inline><code className="value">{serverPort}</code></SettingRow>
        <SettingRow
          label="TMDB search"
          inline
          hint={saved.tmdb_enabled ? undefined : <>Add <code>TMDB_READ_TOKEN</code> to <code>.env</code> and restart the web service.</>}
        >
          <span className={`status-chip ${saved.tmdb_enabled ? 'ready' : 'warn'}`}>{saved.tmdb_enabled ? 'Configured' : 'Token required'}</span>
        </SettingRow>
      </Group>
      <p className="settings-footnote">Open the TV link in the TV's browser and the Phone link to manage movie nights. Use the address on the same network as the device; the Strato's network is usually the TV's.</p>
      <p className="settings-footnote">TMDB supplies movie search and metadata. Only movies you schedule or add to the slideshow are saved locally.</p>

      <div className={`save-bar ${dirty ? 'visible' : ''}`} aria-hidden={!dirty}>
        <span>Unsaved changes</span>
        <button type="button" className="button quiet" onClick={discard} disabled={!dirty || busy} tabIndex={dirty ? 0 : -1}>Discard</button>
        <button type="submit" className="button primary" disabled={!dirty || busy} tabIndex={dirty ? 0 : -1}>{busy ? 'Saving...' : 'Save'}</button>
      </div>
    </form>
  );
}
