import { http, HttpResponse } from "msw";

// A tiny fake backend that mimics the real API's wire format (see tests/test_mock_cases.py).
export const PASSWORD = "Passw0rd!";
export const ADMIN = {
  id: 1,
  email: "admin@example.com",
  first_name: "Admin",
  last_name: "User",
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

const VALID_ACCESS = ["access-1", "access-2"];
const apiError = (status: number, trace_id: string, message: string) =>
  HttpResponse.json({ trace_id, message }, { status });

const isAuthed = (request: Request) =>
  VALID_ACCESS.includes((request.headers.get("Authorization") ?? "").replace("Bearer ", ""));
const expired = () => apiError(401, "middlware-002", "token had expired");

const TOTALS: Record<string, number> = { users: 12, "user-permissions": 27 };

function row(slug: string, id: number) {
  return slug === "users"
    ? { ...ADMIN, id, email: `user${id}@example.com` }
    : { ID: id, UserId: 1, permission: id === 1 ? "admin" : `report:${String(id - 1).padStart(2, "0")}`, updated_at: ADMIN.updated_at };
}

export const handlers = [
  http.post("*/api/v1/users/login", async ({ request }) => {
    const body = (await request.json()) as { email: string; password: string };
    if (body.email !== ADMIN.email) return apiError(400, "users-002", "record not found");
    if (body.password !== PASSWORD) return apiError(400, "users-002", "password is invalid");
    return HttpResponse.json({ user: ADMIN, token: { access: "access-1", refresh: "refresh-1" } });
  }),

  http.post("*/api/v1/users/register", async ({ request }) => {
    const body = (await request.json()) as { email: string };
    if (!/^[\w.-]+@([\w-]+\.)+[\w-]{2,4}$/.test(body.email)) {
      return apiError(400, "users-001", "email pattern is invalid");
    }
    if (body.email === ADMIN.email) return apiError(500, "users-001", "email already registered");
    return HttpResponse.json({ ...ADMIN, id: 99, email: body.email }, { status: 201 });
  }),

  http.post("*/api/v1/users/profile", ({ request }) =>
    isAuthed(request) ? HttpResponse.json(ADMIN) : expired(),
  ),

  http.post("*/api/v1/users/logout", () => HttpResponse.json(null)),

  http.post("*/api/v1/users/refresh-token", async ({ request }) => {
    const body = (await request.json()) as { refresh_token: string };
    if (body.refresh_token !== "refresh-1") return apiError(400, "users-003", "user token not found");
    return HttpResponse.json({ user: ADMIN, token: { access: "access-2", refresh: "refresh-1" } });
  }),

  http.get("*/api/v1/data/:slug/describe", ({ request, params }) =>
    isAuthed(request)
      ? HttpResponse.json({ type: "record", name: `${params.slug}-model`, fields: [] })
      : expired(),
  ),

  http.get("*/api/v1/data/:slug/", ({ request, params }) => {
    if (!isAuthed(request)) return expired();
    const slug = String(params.slug);
    const total = TOTALS[slug];
    if (total === undefined) return apiError(400, "error", "Entity model not found");

    const url = new URL(request.url);
    const page = Number(url.searchParams.get("_page") ?? 1);
    const size = Number(url.searchParams.get("_pageSize") ?? 10);
    const first = (page - 1) * size + 1;
    const last = Math.min(first + size - 1, total);
    const data = Array.from({ length: Math.max(last - first + 1, 0) }, (_, i) => row(slug, first + i));
    return HttpResponse.json({
      code: 0,
      data,
      page,
      page_size: size,
      total_page: 1, // like the real Postgres list: not a reliable page count
      total_data: data.length,
      message: "",
      data_schema: null,
    });
  }),
];
