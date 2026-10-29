// Passes a file picked on one page (e.g. Home) to the Analyze page without
// serialising it into router state. A handoff is only valid briefly so that a
// file restored by an effect cleanup (React Strict Mode remount) is picked up
// again, but never resurfaces on a later visit.
const TTL_MS = 3000;
let pending: { file: File; at: number } | null = null;

export function handOffFile(file: File, at = Date.now()) {
  pending = { file, at };
}

export function takeHandedOffFile(): { file: File; at: number } | null {
  const p = pending;
  pending = null;
  return p && Date.now() - p.at < TTL_MS ? p : null;
}
