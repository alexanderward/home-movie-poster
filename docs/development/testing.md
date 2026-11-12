# Testing

Fast tests use an in-memory SQLite database and avoid network dependencies. They cover discovery
parsing, presentation matching, poster normalization, redaction, schedule labels, and browser
progress correction.

Browser tests use the `browser` marker and Playwright Chromium. Required viewport journeys are
1080x1920, 1920x1080 at both rotation directions, and 390x844.

Before a Raspberry Pi release, also verify TMDB search, real playback, pause, seek, stop, standby,
connection loss, DHCP address changes, service restart, rediscovery, transient-cover replacement,
and all rotations on the actual LG browser.
