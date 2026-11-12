# TV display and rotation

The route `/display` renders a virtual canvas. At 90° and 270° the virtual width and height swap before the transform, so layout is calculated in the television's final orientation. Posters always use containment and remain fully visible.

The display polls the small state endpoint once per second. Playback position advances locally only during `playing` and corrects against each monitor observation.

Idle rotation defaults to 60 seconds. Only movies deliberately added from TMDB or uploaded manually participate. The resolver uses a deterministic shuffle bag so eligible posters do not repeat before the set is exhausted.
