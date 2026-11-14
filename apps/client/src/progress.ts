/**
 * Percent watched. `position` is the server's estimate when the state was fetched; `receivedAt` is when this client
 * fetched it, on this client's clock, so playback advances smoothly between polls without comparing two clocks.
 */
export function calculateProgress(
  position: number,
  duration: number,
  receivedAt: number,
  playing: boolean,
  now = Date.now(),
) {
  const elapsed = playing ? Math.max(0, (now - receivedAt) / 1000) : 0;
  return Math.min(100, Math.max(0, ((position + elapsed) / duration) * 100));
}
