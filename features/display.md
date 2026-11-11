# TV display and rotation

The route `/display` renders a virtual canvas. At 90° and 270° the virtual width and height swap before the transform, so layout is calculated in the television's final orientation. Posters always use containment and remain fully visible.

WebSocket updates are immediate. When the socket disconnects or is unsupported, five-second polling retains the last confirmed state while refreshing. Playback position advances locally only during `playing` and corrects against each monitor observation.

Idle rotation defaults to 60 seconds. Imported Kaleidescape titles participate by default; exclusions remain available in the phone UI. The resolver uses a deterministic shuffle bag so eligible posters do not repeat before the set is exhausted.
