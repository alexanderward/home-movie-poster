import { type FormEvent, useEffect, useMemo, useState } from 'react';
import { api, jsonBody } from '../api';
import type {
  ApplicationSettingsInput,
  ApplicationSettingsView,
  DeviceRolesInput,
  DiscoveredDeviceView,
  LibrarySyncStatus,
} from '../contracts.generated';
import { errorMessage, type Notify } from './shared';

const timeZones: string[] =
  (Intl as unknown as { supportedValuesOf?: (key: string) => string[] }).supportedValuesOf?.('timeZone') ?? [];

function displayDraft(row: ApplicationSettingsView): ApplicationSettingsInput {
  return { rotation: row.rotation, slideshow_interval_seconds: row.slideshow_interval_seconds, timezone: row.timezone };
}

function rolesDraft(row: ApplicationSettingsView): DeviceRolesInput {
  return { player_serial: row.player_serial, library_serial: row.library_serial, manual_host: row.manual_host };
}

const same = (left: object, right: object) => JSON.stringify(left) === JSON.stringify(right);

export function SettingsTab({ notify }: { notify: Notify }) {
  const [saved, setSaved] = useState<ApplicationSettingsView | null>(null);
  const [display, setDisplay] = useState<ApplicationSettingsInput | null>(null);
  const [roles, setRoles] = useState<DeviceRolesInput | null>(null);
  const [devices, setDevices] = useState<DiscoveredDeviceView[] | null>(null);
  const [sync, setSync] = useState<LibrarySyncStatus | null>(null);
  const [busy, setBusy] = useState<'display' | 'roles' | 'sync' | null>(null);

  useEffect(() => {
    Promise.all([
      api<ApplicationSettingsView>('/api/settings'),
      api<DiscoveredDeviceView[]>('/api/devices'),
      api<LibrarySyncStatus | null>('/api/library-sync'),
    ]).then(([nextSettings, nextDevices, nextSync]) => {
      setSaved(nextSettings);
      setDisplay(displayDraft(nextSettings));
      setRoles(rolesDraft(nextSettings));
      setDevices(nextDevices);
      setSync(nextSync);
    }).catch((caught) => notify(errorMessage(caught, 'Could not load settings.'), 'error'));
  }, [notify]);

  const syncActive = sync?.status === 'queued' || sync?.status === 'running';
  useEffect(() => {
    if (!syncActive) return;
    const timer = window.setInterval(() => {
      api<LibrarySyncStatus | null>('/api/library-sync').then((next) => {
        setSync(next);
        if (next?.status === 'succeeded') notify(`Library sync finished: ${next.discovered_count} found, ${next.updated_count} updated.`);
        if (next?.status === 'failed') notify(`Library sync failed: ${next.error || 'unknown error'}`, 'error');
      }).catch(() => undefined);
    }, 3000);
    return () => window.clearInterval(timer);
  }, [syncActive, notify]);

  const displayDirty = useMemo(() => Boolean(saved && display && !same(displayDraft(saved), display)), [saved, display]);
  const rolesDirty = useMemo(() => Boolean(saved && roles && !same(rolesDraft(saved), roles)), [saved, roles]);

  async function save(kind: 'display' | 'roles', event: FormEvent) {
    event.preventDefault();
    const [path, body, message] = kind === 'display'
      ? ['/api/settings', display, 'Display settings saved.'] as const
      : ['/api/devices/roles', roles, 'Device roles saved.'] as const;
    if (!body) return;
    setBusy(kind);
    try {
      const next = await api<ApplicationSettingsView>(path, { method: 'PUT', body: jsonBody(body) });
      setSaved(next);
      if (kind === 'display') setDisplay(displayDraft(next)); else setRoles(rolesDraft(next));
      notify(message);
    } catch (caught) {
      notify(errorMessage(caught, 'Could not save settings.'), 'error');
    } finally {
      setBusy(null);
    }
  }

  async function startSync() {
    setBusy('sync');
    try {
      setSync(await api<LibrarySyncStatus>('/api/library-sync', { method: 'POST' }));
      notify('Library sync queued.');
    } catch (caught) {
      notify(errorMessage(caught, 'Could not start library sync.'), 'error');
    } finally {
      setBusy(null);
    }
  }

  if (!display || !roles || !devices) {
    return <div className="tab-body"><h1 className="tab-title">Settings</h1><p className="muted">Loading…</p></div>;
  }

  return (
    <div className="tab-body">
      <h1 className="tab-title">Settings</h1>
      <div className="settings-grid">
        <section className="card">
          <h2>Television</h2>
          <form onSubmit={(event) => void save('display', event)} className="form-stack">
            <fieldset>
              <legend>Rotation</legend>
              <div className="segmented">
                {([0, 90, 270] as const).map((value) => (
                  <label key={value}><input type="radio" name="rotation" checked={display.rotation === value} onChange={() => setDisplay({ ...display, rotation: value })} /><span>{value}°</span></label>
                ))}
              </div>
            </fieldset>
            <label>
              <span className="label-split">Poster interval <output>{display.slideshow_interval_seconds}s</output></span>
              <input type="range" min="10" max="300" step="5" value={display.slideshow_interval_seconds} onChange={(event) => setDisplay({ ...display, slideshow_interval_seconds: Number(event.target.value) })} />
            </label>
            <label>Timezone
              <input list="timezones" value={display.timezone} onChange={(event) => setDisplay({ ...display, timezone: event.target.value })} />
              <datalist id="timezones">{timeZones.map((zone) => <option key={zone} value={zone} />)}</datalist>
            </label>
            <button className="button primary" disabled={!displayDirty || busy === 'display'}>{busy === 'display' ? 'Saving…' : displayDirty ? 'Save display settings' : 'Saved'}</button>
          </form>
        </section>

        <section className="card">
          <div className="card-heading">
            <h2>Kaleidescape</h2>
            <span className={`status-chip ${devices.length ? 'ready' : ''}`}>{devices.length ? `${devices.length} found` : 'Searching'}</span>
          </div>
          {devices.length === 0 ? (
            <div className="device-empty">
              <strong>No player found yet</strong>
              <p>Discovery is scanning this LAN. On Windows, stop the Docker monitor and run <code>uv run poster monitor</code> natively. You can also enter a hostname below.</p>
            </div>
          ) : (
            <div className="row-list">
              {devices.map((device) => (
                <article className="row" key={device.serial_number}>
                  <div className="grow">
                    <strong>{device.friendly_name || device.serial_number}</strong>
                    <small>{[device.device_type, device.ip_address].filter(Boolean).join(' · ')}</small>
                  </div>
                  {device.selected_as_player && <span className="status-chip ready">Player</span>}
                  {device.selected_as_library && <span className="status-chip ready">Library</span>}
                </article>
              ))}
            </div>
          )}
          <form onSubmit={(event) => void save('roles', event)} className="form-stack spaced">
            <label>Playback player
              <select value={roles.player_serial} onChange={(event) => setRoles({ ...roles, player_serial: event.target.value })}>
                <option value="">Auto-select</option>
                {devices.filter((device) => device.supports_playback).map((device) => <option value={device.serial_number} key={device.serial_number}>{device.friendly_name || device.serial_number}</option>)}
              </select>
            </label>
            <label>Library host
              <select value={roles.library_serial} onChange={(event) => setRoles({ ...roles, library_serial: event.target.value })}>
                <option value="">Auto-select</option>
                {devices.filter((device) => device.supports_library).map((device) => <option value={device.serial_number} key={device.serial_number}>{device.friendly_name || device.serial_number}</option>)}
              </select>
            </label>
            <label><span>Manual hostname <span className="optional">fallback</span></span>
              <input value={roles.manual_host} onChange={(event) => setRoles({ ...roles, manual_host: event.target.value })} placeholder="kplayer.local" autoCapitalize="off" autoCorrect="off" spellCheck={false} />
            </label>
            <button className="button primary" disabled={!rolesDirty || busy === 'roles'}>{busy === 'roles' ? 'Saving…' : rolesDirty ? 'Save device roles' : 'Saved'}</button>
          </form>
          <div className="sync-row">
            <div>
              <strong>Library sync</strong>
              <small>{sync ? `${syncActive ? 'In progress' : sync.status === 'failed' ? 'Failed' : 'Last run'} · ${sync.updated_count} updated${sync.finished_at ? ` · ${new Date(sync.finished_at).toLocaleString()}` : ''}` : 'Not run yet'}</small>
            </div>
            <button className="button quiet" disabled={syncActive || busy === 'sync'} onClick={() => void startSync()}>{syncActive ? 'Syncing…' : 'Sync now'}</button>
          </div>
        </section>
      </div>
    </div>
  );
}
