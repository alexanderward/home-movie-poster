/* Generated from Pydantic contracts. Do not hand-edit. */

export interface DisplayState {
  mode: "now_playing" | "scheduled" | "rotation" | "setup";
  headline: string;
  title: string;
  poster_url: string | null;
  event_date: string | null;
  showtime: string | null;
  playback_status: string | null;
  position_seconds: number | null;
  duration_seconds: number | null;
  observed_at: string | null;
  rotation: 0 | 90 | 270;
  slideshow_interval_seconds: number;
}

export interface MovieSummary {
  id: number;
  source: "tmdb" | "manual";
  source_key: string;
  title: string;
  year: number | null;
  poster_url: string | null;
  include_in_rotation: boolean;
}

export interface MovieDetail {
  id: number;
  source: "tmdb" | "manual";
  source_key: string;
  title: string;
  year: number | null;
  poster_url: string | null;
  include_in_rotation: boolean;
}

export interface MoviePage {
  items: Array<MovieSummary>;
  page: number;
  page_size: number;
  total: number;
}

export interface MovieUpdate {
  include_in_rotation: boolean | null;
}

export interface MovieNightInput {
  movie_id: number;
  event_date: string;
  showtime: string | null;
}

export interface MovieNightView {
  id: number;
  movie: MovieSummary;
  event_date: string;
  showtime: string | null;
  archived: boolean;
}

export interface DiscoveredDeviceView {
  serial_number: string;
  friendly_name: string;
  device_type: string;
  ip_address: string;
  supports_playback: boolean;
  selected_as_player: boolean;
  last_seen_at: string;
}

export interface PlayerSettingsInput {
  player_serial: string;
  manual_host: string;
}

export interface ApplicationSettingsInput {
  rotation: 0 | 90 | 270;
  slideshow_interval_seconds: number;
  timezone: string;
}

export interface ApplicationSettingsView {
  rotation: 0 | 90 | 270;
  slideshow_interval_seconds: number;
  timezone: string;
  player_serial: string;
  manual_host: string;
  tmdb_enabled: boolean;
}

export interface SessionView {
  csrf_token: string;
  tmdb_enabled: boolean;
}

export interface HealthView {
  status: "ok" | "degraded";
  database: boolean;
  monitor: boolean;
  player_connected: boolean;
  tmdb_configured: boolean;
}

export interface PosterSearchResult {
  key: string;
  title: string;
  year: number | null;
  poster_url: string | null;
  sources: Array<"tmdb" | "manual">;
  movie_id: number | null;
  tmdb_id: number | null;
  include_in_rotation: boolean;
}

export interface PosterSearch {
  query: string;
  results: Array<PosterSearchResult>;
  tmdb: "ok" | "disabled" | "unavailable";
}

export interface SlideshowView {
  total: number;
  interval_seconds: number;
  items: Array<MovieSummary>;
}
