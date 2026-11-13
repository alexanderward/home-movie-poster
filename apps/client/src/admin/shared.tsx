import { useEffect, useState } from 'react';

export interface ToastAction { label: string; run: () => void }
export type Notify = (text: string, kind?: 'success' | 'error', action?: ToastAction) => void;

export function errorMessage(caught: unknown, fallback: string) {
  return caught instanceof Error ? caught.message : fallback;
}

/** Returns `value` once it has stopped changing for `delay` milliseconds. */
export function useDebounced<T>(value: T, delay = 250) {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(value), delay);
    return () => window.clearTimeout(timer);
  }, [value, delay]);
  return debounced;
}

export function isoDate(date: Date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
}

export function nextFriday() {
  const date = new Date();
  const delta = (5 - date.getDay() + 7) % 7 || 7;
  date.setDate(date.getDate() + delta);
  return isoDate(date);
}

export function dateLabel(value: string, showtime: string | null) {
  const date = new Date(`${value}T12:00:00`);
  const label = date.toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' });
  if (!showtime) return label;
  const time = new Date(`2000-01-01T${showtime}`).toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' });
  return `${label} · ${time}`;
}

export function PosterThumb({ url, fallback = 'F' }: { url: string | null; fallback?: string }) {
  return <div className="poster-thumb">{url ? <img src={url} alt="" loading="lazy" /> : <span>{fallback}</span>}</div>;
}
