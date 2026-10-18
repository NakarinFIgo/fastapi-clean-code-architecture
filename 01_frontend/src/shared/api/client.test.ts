import { http, HttpResponse } from "msw";

import { ApiError, request } from "./client";
import { clearTokens, loadTokens, saveTokens } from "./token_store";
import { server } from "../../test/server";

describe("request", () => {
  it("turns the API error body into an ApiError", async () => {
    server.use(
      http.get("*/api/v1/thing", () =>
        HttpResponse.json({ trace_id: "users-002", message: "password is invalid" }, { status: 400 }),
      ),
    );

    const err = (await request("/thing").catch((e: unknown) => e)) as ApiError;

    expect(err).toBeInstanceOf(ApiError);
    expect(err).toMatchObject({ status: 400, traceId: "users-002", message: "password is invalid" });
    expect(err.display).toBe("users-002: password is invalid");
  });

  it("reports a network failure with status 0", async () => {
    server.use(http.get("*/api/v1/thing", () => HttpResponse.error()));

    await expect(request("/thing")).rejects.toMatchObject({ status: 0, traceId: "network" });
  });

  it("sends the Bearer token only for authenticated calls", async () => {
    saveTokens({ access: "access-1", refresh: "refresh-1" });
    const seen: Array<string | null> = [];
    server.use(
      http.get("*/api/v1/thing", ({ request: r }) => {
        seen.push(r.headers.get("Authorization"));
        return HttpResponse.json({});
      }),
    );

    await request("/thing");
    await request("/thing", { auth: true });

    expect(seen).toEqual([null, "Bearer access-1"]);
  });

  it("does not try to refresh on a 401 from an unauthenticated call", async () => {
    let refreshCalls = 0;
    server.use(
      http.get("*/api/v1/thing", () => HttpResponse.json({ trace_id: "x", message: "no" }, { status: 401 })),
      http.post("*/api/v1/refresh-token", () => {
        refreshCalls += 1;
        return HttpResponse.json({});
      }),
    );
    saveTokens({ access: "a", refresh: "refresh-1" });

    await expect(request("/thing")).rejects.toMatchObject({ status: 401 });
    expect(refreshCalls).toBe(0);
  });

  it("refreshes only once even if the retry is also rejected", async () => {
    let refreshCalls = 0;
    server.use(
      http.get("*/api/v1/thing", () => HttpResponse.json({ trace_id: "x", message: "still no" }, { status: 401 })),
      http.post("*/api/v1/refresh-token", () => {
        refreshCalls += 1;
        return HttpResponse.json({ user: {}, token: { access: "access-2", refresh: "refresh-1" } });
      }),
    );
    saveTokens({ access: "stale", refresh: "refresh-1" });

    await expect(request("/thing", { auth: true })).rejects.toMatchObject({ status: 401 });
    expect(refreshCalls).toBe(1);
    expect(loadTokens()).toBeNull(); // session ended
  });
});

describe("tokenStore", () => {
  it("round-trips and clears", () => {
    saveTokens({ access: "a", refresh: "r" });
    expect(loadTokens()).toEqual({ access: "a", refresh: "r" });
    clearTokens();
    expect(loadTokens()).toBeNull();
  });

  it("does not throw when sessionStorage is unavailable", () => {
    const boom = vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    const boomSet = vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("blocked");
    });

    expect(loadTokens()).toBeNull();
    expect(() => saveTokens({ access: "a", refresh: "r" })).not.toThrow();

    boom.mockRestore();
    boomSet.mockRestore();
  });

  it("ignores corrupt JSON", () => {
    sessionStorage.setItem("tokens", "{not json");
    expect(loadTokens()).toBeNull();
  });
});
