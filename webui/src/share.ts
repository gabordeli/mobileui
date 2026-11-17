const MAGNET_RE = /magnet:\?[^\s"'<>]+/i;

export function extractMagnet(search: string): string {
  const params = new URLSearchParams(search);
  for (const key of ["text", "url", "title"]) {
    const value = params.get(key);
    if (!value) continue;
    const match = MAGNET_RE.exec(value);
    if (match) return match[0];
  }
  return "";
}
