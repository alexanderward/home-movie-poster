# Testing

Fast tests avoid network and database dependencies. They cover protocol/HTML parsing, matching, poster normalization, redaction, schedule labels, and browser progress correction.

PostgreSQL tests use the `postgres` marker and a disposable CI service. Browser tests use the `browser` marker and Playwright Chromium. Required viewport journeys are 1080×1920, 1920×1080 at both rotation directions, and 390×844.

Before a Raspberry Pi release, also verify real playback, pause, seek, stop, standby, connection loss, DHCP address changes, service restart, rediscovery, library retention after malformed HTML, and all rotations on the actual LG browser.
