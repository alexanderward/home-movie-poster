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
  source: "kaleidescape" | "tmdb" | "manual";
  source_key: string;
  title: string;
  year: number | null;
  poster_url: string | null;
  include_in_rotation: boolean;
  available: boolean;
}

export interface MovieDetail {
  id: number;
  source: "kaleidescape" | "tmdb" | "manual";
  source_key: string;
  title: string;
  year: number | null;
  poster_url: string | null;
  include_in_rotation: boolean;
  available: boolean;
  genre: string;
  rating: string;
  director: string;
  synopsis: string;
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
  supports_library: boolean;
  selected_as_player: boolean;
  selected_as_library: boolean;
  last_seen_at: string;
}

export interface DeviceRolesInput {
  player_serial: string;
  library_serial: string;
  manual_host: string;
}

export interface LibrarySyncStatus {
  id: number;
  status: "queued" | "running" | "succeeded" | "failed";
  requested_at: string;
  started_at: string | null;
  finished_at: string | null;
  discovered_count: number;
  updated_count: number;
  error: string;
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
  library_serial: string;
  manual_host: string;
  tmdb_enabled: boolean;
}

export interface SessionView {
  csrf_token: string;
  tmdb_enabled: boolean;
  websocket_path: string;
}

export interface HealthView {
  status: "ok" | "degraded";
  database: boolean;
  redis: boolean;
  monitor: boolean;
  player_connected: boolean;
  last_library_sync: string | null;
}

export interface TmdbMovie {
  id: number;
  title: string;
  year: number | null;
  overview: string;
  poster_url: string | null;
}

export interface PosterSearchResult {
  key: string;
  title: string;
  year: number | null;
  poster_url: string | null;
  sources: Array<"kaleidescape" | "tmdb" | "manual">;
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
