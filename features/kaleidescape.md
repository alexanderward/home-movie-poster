# Kaleidescape discovery and monitoring

The dedicated monitor actively searches SDDP, accepts passive replies, listens to legacy heartbeats on UDP 1443, and probes candidates with `pykaleidescape`. Auto-selection occurs only when one role candidate exists. Multiple candidates remain visible in the phone UI until the user chooses serial-number roles.

One event-driven device connection follows playback. Playing, paused, scan-forward, and scan-reverse are active. Each observation is saved and broadcast. Disconnect retains the last active state for 30 seconds.

Library synchronization runs at startup, every six hours, and when queued by the UI. The `/movies` adapter extracts selection handles, then up to four concurrent content-detail calls resolve metadata and art. A failed or zero-result sync never replaces the last good library.
