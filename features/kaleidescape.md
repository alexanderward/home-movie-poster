# Kaleidescape discovery and monitoring

The dedicated monitor actively searches SDDP, accepts passive replies, listens to legacy heartbeats on UDP 1443, and probes candidates with `pykaleidescape`. Auto-selection occurs only when one playback candidate exists. Multiple candidates remain visible in the phone UI until the user chooses a player by serial number.

One event-driven, read-only connection follows playback. Playing, paused, scan-forward, and scan-reverse are active. Each observation updates a single transient snapshot in SQLite. Disconnect retains the last active state for 30 seconds.

The monitor never enumerates or imports the Kaleidescape library. Current cover art is proxied through one replaceable runtime image so the television does not need direct access to the player subnet.
