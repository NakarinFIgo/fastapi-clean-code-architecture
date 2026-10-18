import type { TokenPair } from "./types";

const KEY = "tokens";

// sessionStorage can throw (private mode, blocked storage); the app must still work without it.
export function loadTokens(): TokenPair | null {
  try {
    const raw = sessionStorage.getItem(KEY);
    return raw ? (JSON.parse(raw) as TokenPair) : null;
  } catch {
    return null;
  }
}

export function saveTokens(tokens: TokenPair): void {
  try {
    sessionStorage.setItem(KEY, JSON.stringify(tokens));
  } catch {
    /* keep going without persistence */
  }
}

export function clearTokens(): void {
  try {
    sessionStorage.removeItem(KEY);
  } catch {
    /* nothing to clear */
  }
}
