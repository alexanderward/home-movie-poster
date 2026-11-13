import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { api } from '../api';
import type { HealthView } from '../contracts.generated';
import { Home } from './Home';
import { SettingsTab } from './SettingsTab';
import type { Notify, ToastAction } from './shared';

interface Toast { id: number; text: string; kind: 'success' | 'error'; action?: ToastAction }

export function Admin() {
  const [params, setParams] = useSearchParams();
  const showSettings = params.get('view') === 'settings';
  const [health, setHealth] = useState<HealthView | null>(null);
  const [toast, setToast] = useState<Toast | null>(null);
  const toastId = useRef(0);

  useEffect(() => {
    api<HealthView>('/api/health').then(setHealth).catch(() => setHealth(null));
  }, []);

  useEffect(() => {
    if (!toast || toast.kind === 'error') return;
    const timer = window.setTimeout(() => setToast(null), toast.action ? 6000 : 3000);
    return () => window.clearTimeout(timer);
  }, [toast]);

  const notify = useCallback<Notify>((text, kind = 'success', action) => {
    toastId.current += 1;
    setToast({ id: toastId.current, text, kind, action });
  }, []);

  const playerReady = Boolean(health?.player_connected);

  return (
    <main className="admin-shell">
      <header className="admin-header">
        <button type="button" className="admin-brand" onClick={() => setParams({}, { replace: true })}>
          <span className="brand-mark">F</span><strong>Frame</strong>
        </button>
        <div className="header-actions">
          <span className={`live-pill ${playerReady ? 'ready' : ''}`} title={health ? `Monitor ${health.monitor ? 'running' : 'stopped'}` : undefined}>
            <i />{playerReady ? 'Player connected' : 'Player offline'}
          </span>
          <Link className="button quiet" to="/display" target="_blank">Display <span aria-hidden="true">↗</span></Link>
          <button
            type="button"
            className={`button quiet settings-button ${showSettings ? 'active' : ''}`}
            aria-pressed={showSettings}
            onClick={() => setParams(showSettings ? {} : { view: 'settings' }, { replace: true })}
          >
            <svg viewBox="0 0 20 20" aria-hidden="true"><circle cx="10" cy="10" r="2.6" /><path d="M10 2.5v2M10 15.5v2M2.5 10h2M15.5 10h2M4.7 4.7l1.4 1.4M13.9 13.9l1.4 1.4M4.7 15.3l1.4-1.4M13.9 6.1l1.4-1.4" /></svg>
            <span className="settings-label">Settings</span>
          </button>
        </div>
      </header>

      <div className="toast-region" aria-live="polite">
        {toast && (
          <p key={toast.id} className={`alert ${toast.kind}`} role={toast.kind === 'error' ? 'alert' : 'status'}>
            <span>{toast.text}</span>
            {toast.action && <button className="alert-action" onClick={() => { toast.action?.run(); setToast(null); }}>{toast.action.label}</button>}
            <button className="alert-close" aria-label="Dismiss" onClick={() => setToast(null)}>×</button>
          </p>
        )}
      </div>

      {showSettings ? (
        <>
          <button type="button" className="back-link" onClick={() => setParams({}, { replace: true })}>← Back</button>
          <SettingsTab notify={notify} />
        </>
      ) : <Home notify={notify} />}
    </main>
  );
}
