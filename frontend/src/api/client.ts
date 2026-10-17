import { clearTokens, loadTokens, saveTokens } from "./tokenStore";
import type { LoginResponse } from "./types";

const BASE = "/api/v1";

/** Error shape the backend returns: {"trace_id": "...", "message": "..."} */
export class ApiError extends Error {
  readonly status: number;
  readonly traceId: string;

  constructor(status: number, traceId: string, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.traceId = traceId;
  }

  get display(): string {
    return `${this.traceId}: ${this.message}`;
  }
}

let onSessionExpired: () => void = () => {};

export function setSessionExpiredHandler(handler: () => void): void {
  onSessionExpired = handler;
}

interface RequestOptions {
  method?: "GET" | "POST";
  body?: unknown;
  auth?: boolean;
}

async function send(path: string, options: RequestOptions, accessToken?: string): Promise<Response> {
  const headers: Record<string, string> = {};
  if (options.body !== undefined) headers["Content-Type"] = "application/json";
  if (accessToken) headers.Authorization = `Bearer ${accessToken}`;
  // new URL() because Node's fetch (used in tests) has no base to resolve relative paths against.
  const url = new URL(`${BASE}${path}`, window.location.href).toString();
  try {
    return await fetch(url, {
      method: options.method ?? "GET",
      headers,
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
    });
  } catch {
    throw new ApiError(0, "network", "Cannot reach the server");
  }
}

async function toApiError(res: Response): Promise<ApiError> {
  let traceId = "error";
  let message = res.statusText || "Request failed";
  try {
    const body = (await res.json()) as { trace_id?: string; message?: string };
    traceId = body.trace_id ?? traceId;
    message = body.message ?? message;
  } catch {
    /* body was not JSON */
  }
  return new ApiError(res.status, traceId, message);
}

async function refreshTokens(): Promise<boolean> {
  const tokens = loadTokens();
  if (!tokens) return false;
  try {
    const res = await send("/users/refresh-token", {
      method: "POST",
      body: { refresh_token: tokens.refresh },
    });
    if (!res.ok) return false;
    saveTokens(((await res.json()) as LoginResponse).token);
    return true;
  } catch {
    return false;
  }
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  let res = await send(path, options, options.auth ? loadTokens()?.access : undefined);

  // Expired access token: refresh once, then retry the original call.
  if (res.status === 401 && options.auth) {
    if (await refreshTokens()) {
      res = await send(path, options, loadTokens()?.access);
    }
    if (res.status === 401) {
      clearTokens();
      onSessionExpired();
    }
  }

  if (!res.ok) throw await toApiError(res);
  const text = await res.text();
  return (text ? JSON.parse(text) : undefined) as T;
}
