export function calculateProgress(
  position: number,
  duration: number,
  observed: string,
  playing: boolean,
  now = Date.now(),
) {
  const elapsed = playing ? Math.max(0, (now - new Date(observed).getTime()) / 1000) : 0;
  return Math.min(100, Math.max(0, ((position + elapsed) / duration) * 100));
}
