/**
 * i18n helpers: {placeholder} interpolation + localStorage persistence.
 *
 * The reactive ``t`` store lives in ``$stores/index``; this module adds the
 * non-reactive pieces (interpolation + storage) and is imported by the layout
 * bootstrap and the language switcher. Keeping these as plain functions avoids
 * pulling store machinery into places that only need a static lookup.
 */

/** localStorage key for the user's chosen language code. */
export const LANG_STORAGE_KEY = 'pst-lang';

/** Interpolate ``{name}`` placeholders in a template string. */
export function interpolate(
  template: string,
  params?: Record<string, string | number>,
): string {
  if (!params) return template;
  return template.replace(/\{(\w+)\}/g, (_, key: string) =>
    key in params ? String(params[key]) : `{${key}}`,
  );
}

/** Read the persisted language code, or ``null`` if never set. */
export function getStoredLang(): string | null {
  if (typeof localStorage === 'undefined') return null;
  try {
    return localStorage.getItem(LANG_STORAGE_KEY);
  } catch {
    return null; // localStorage may be disabled (private mode, sandbox)
  }
}

/** Persist the language code so it survives reloads. */
export function setStoredLang(code: string): void {
  if (typeof localStorage === 'undefined') return;
  try {
    localStorage.setItem(LANG_STORAGE_KEY, code);
  } catch {
    // ignore write failures (quota, private mode)
  }
}

/** Clear the persisted language (revert to server default on next load). */
export function clearStoredLang(): void {
  if (typeof localStorage === 'undefined') return;
  try {
    localStorage.removeItem(LANG_STORAGE_KEY);
  } catch {
    // ignore
  }
}
