import axios, { type AxiosResponse } from "axios";

import { API_BASE_URL } from "../config/env";
import { clearTokens, loadTokens, saveTokens } from "./token_store";
import type { TokenPair } from "./types";

// validateStatus accepts every status so request() can read the error body and handle 401 itself.
const http = axios.create({ baseURL: API_BASE_URL, validateStatus: () => true });

const isOk = (res: AxiosResponse): boolean => res.status >= 200 && res.status < 300;

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

async function send(
  path: string,
  options: RequestOptions,
  accessToken?: string,
): Promise<AxiosResponse> {
  try {
    return await http.request({
      url: path,
      method: options.method ?? "GET",
      data: options.body,
      headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : undefined,
    });
  } catch {
    throw new ApiError(0, "network", "Cannot reach the server");
  }
}

function toApiError(res: AxiosResponse): ApiError {
  const body = res.data as { trace_id?: string; message?: string } | null;
  return new ApiError(
    res.status,
    body?.trace_id ?? "error",
    body?.message ?? (res.statusText || "Request failed"),
  );
}

async function refreshTokens(): Promise<boolean> {
  const tokens = loadTokens();
  if (!tokens) return false;
  try {
    const res = await send("/refresh-token", {
      method: "POST",
      body: { refresh_token: tokens.refresh },
    });
    if (!isOk(res)) return false;
    saveTokens((res.data as { token: TokenPair }).token);
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

  if (!isOk(res)) throw toApiError(res);
  return (res.data === "" ? undefined : res.data) as T;
}
