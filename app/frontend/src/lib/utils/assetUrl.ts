const FALLBACK_PATH = 'icons/T_icon_unknown.webp';
const BASE = '/api/data/game-data-asset/';

export function assetUrl(path: string | null | undefined): string {
  return BASE + (path ?? FALLBACK_PATH).replace(/^\//, '');
}

export function imgOnError(e: Event): void {
  const img = e.currentTarget as HTMLImageElement | null;
  if (img && !img.src.includes(FALLBACK_PATH)) {
    img.src = assetUrl(null);
  }
}
