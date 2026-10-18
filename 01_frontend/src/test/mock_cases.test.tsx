/**
 * Scenario suite: what a person clicking through the UI would hit, against a fake backend.
 * Case ids mirror tests/test_mock_cases.py where the scenario exists on both sides.
 */
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";

import App from "../app";
import { ADMIN, PASSWORD } from "./handlers";
import { server } from "./server";

const user = userEvent.setup();

function renderApp() {
  return render(<App />);
}

async function logIn(email = ADMIN.email, password = PASSWORD) {
  await user.type(screen.getByLabelText("Email"), email);
  await user.type(screen.getByLabelText("Password"), password);
  // The tab has role="tab", so the only *button* named "Log in" is the submit button.
  await user.click(screen.getByRole("button", { name: "Log in" }));
}

const storedTokens = () => JSON.parse(sessionStorage.getItem("tokens") ?? "null");

describe("mc01 admin logs in", () => {
  it("shows the profile and the first page of users", async () => {
    renderApp();
    await logIn();

    expect(await screen.findByRole("heading", { name: "Profile" })).toBeInTheDocument();
    expect(screen.getByText("Admin User")).toBeInTheDocument();
    expect(await screen.findByText("user1@example.com")).toBeInTheDocument();
    expect(screen.queryByLabelText("Password")).not.toBeInTheDocument();
  });
});

describe("login errors", () => {
  it("mc02 wrong password shows the API error", async () => {
    renderApp();
    await logIn(ADMIN.email, "nope");
    expect(await screen.findByRole("alert")).toHaveTextContent("users-002: password is invalid");
  });

  it("mc03 unknown user shows the API error", async () => {
    renderApp();
    await logIn("ghost@example.com", "x");
    expect(await screen.findByRole("alert")).toHaveTextContent("users-002: record not found");
  });

  it("mc20 server unreachable shows a network message", async () => {
    server.use(http.post("*/api/v1/login", () => HttpResponse.error()));
    renderApp();
    await logIn();
    expect(await screen.findByRole("alert")).toHaveTextContent("network: Cannot reach the server");
  });

  it("mc21 an HTML 500 from a proxy still produces a readable error", async () => {
    server.use(
      http.post("*/api/v1/login", () =>
        new HttpResponse("<html>boom</html>", { status: 500, statusText: "Internal Server Error" }),
      ),
    );
    renderApp();
    await logIn();
    expect(await screen.findByRole("alert")).toHaveTextContent("error: Internal Server Error");
  });
});

describe("register", () => {
  async function openRegister(email: string) {
    await user.click(screen.getByRole("tab", { name: "Register" }));
    await user.type(screen.getByLabelText("Email"), email);
    await user.type(screen.getByLabelText("Password"), "pw123456");
    await user.click(screen.getByRole("button", { name: "Register" }));
  }

  it("mc07 a new user registers and is sent back to log in", async () => {
    renderApp();
    await openRegister("new@example.com");
    expect(await screen.findByRole("status")).toHaveTextContent("Registered. You can log in now.");
    expect(screen.getByRole("heading", { name: "Welcome back" })).toBeInTheDocument();
  });

  it("mc04 a bad email shows the validation error", async () => {
    renderApp();
    await openRegister("plainaddress");
    expect(await screen.findByRole("alert")).toHaveTextContent("users-001: email pattern is invalid");
  });

  it("mc06 a duplicate email shows the server error", async () => {
    renderApp();
    await openRegister(ADMIN.email);
    expect(await screen.findByRole("alert")).toHaveTextContent("users-001: email already registered");
  });
});

describe("tokens", () => {
  it("mc08 an expired access token is refreshed once and the call is retried", async () => {
    renderApp();
    await logIn();
    await screen.findByText("user1@example.com");

    sessionStorage.setItem("tokens", JSON.stringify({ access: "stale", refresh: "refresh-1" }));
    await user.selectOptions(screen.getByLabelText("Collection"), "user-permissions");

    expect(await screen.findByText("report:01")).toBeInTheDocument();
    expect(storedTokens().access).toBe("access-2");
  });

  it("mc09 when refresh fails the session ends and the login page explains why", async () => {
    renderApp();
    await logIn();
    await screen.findByText("user1@example.com");

    sessionStorage.setItem("tokens", JSON.stringify({ access: "stale", refresh: "bad" }));
    await user.selectOptions(screen.getByLabelText("Collection"), "user-permissions");

    expect(await screen.findByText(/session expired/i)).toBeInTheDocument();
    expect(screen.getByLabelText("Password")).toBeInTheDocument();
    expect(storedTokens()).toBeNull();
  });

  it("mc14 a saved session is restored after a page reload", async () => {
    sessionStorage.setItem("tokens", JSON.stringify({ access: "access-1", refresh: "refresh-1" }));
    renderApp();

    expect(await screen.findByRole("heading", { name: "Profile" })).toBeInTheDocument();
    expect(screen.queryByLabelText("Password")).not.toBeInTheDocument();
  });

  it("mc15 a saved but dead session falls back to the login form", async () => {
    sessionStorage.setItem("tokens", JSON.stringify({ access: "stale", refresh: "bad" }));
    renderApp();

    expect(await screen.findByLabelText("Password")).toBeInTheDocument();
    expect(storedTokens()).toBeNull();
  });

  it("mc13 logging out calls the API and clears the session", async () => {
    let logoutBody: unknown;
    server.use(
      http.post("*/api/v1/logout", async ({ request }) => {
        logoutBody = await request.json();
        return HttpResponse.json(null);
      }),
    );
    renderApp();
    await logIn();
    await screen.findByRole("heading", { name: "Profile" });

    await user.click(screen.getByRole("button", { name: "Log out" }));

    expect(await screen.findByLabelText("Password")).toBeInTheDocument();
    expect(logoutBody).toEqual({ refresh_token: "refresh-1" });
    expect(storedTokens()).toBeNull();
  });

  it("mc22 logging out still works when the server is down", async () => {
    server.use(http.post("*/api/v1/logout", () => HttpResponse.error()));
    renderApp();
    await logIn();
    await screen.findByRole("heading", { name: "Profile" });

    await user.click(screen.getByRole("button", { name: "Log out" }));

    expect(await screen.findByLabelText("Password")).toBeInTheDocument();
  });
});

describe("data browser", () => {
  async function openBrowser() {
    renderApp();
    await logIn();
    await screen.findByText("user1@example.com");
  }

  const bodyRows = () => within(screen.getByRole("table")).getAllByRole("row").slice(1);

  it("mc11 pages forward and back; Next disables on a short page", async () => {
    await openBrowser();
    expect(bodyRows()).toHaveLength(10);
    expect(screen.getByRole("button", { name: "Next" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Previous" })).toBeDisabled();

    await user.click(screen.getByRole("button", { name: "Next" }));
    expect(await screen.findByText("user11@example.com")).toBeInTheDocument();
    expect(bodyRows()).toHaveLength(2); // 12 users: 10 + 2
    expect(screen.getByRole("button", { name: "Next" })).toBeDisabled();

    await user.click(screen.getByRole("button", { name: "Previous" }));
    expect(await screen.findByText("user1@example.com")).toBeInTheDocument();
  });

  it("mc15b the permissions collection pages 10 + 10 + 7", async () => {
    await openBrowser();
    await user.selectOptions(screen.getByLabelText("Collection"), "user-permissions");
    await screen.findByText("report:01");
    await user.click(screen.getByRole("button", { name: "Next" }));
    await screen.findByText("report:10");
    await user.click(screen.getByRole("button", { name: "Next" }));
    await screen.findByText("report:20");
    expect(bodyRows()).toHaveLength(7);
    expect(screen.getByRole("button", { name: "Next" })).toBeDisabled();
  });

  it("changing rows per page goes back to page 1", async () => {
    await openBrowser();
    await user.click(screen.getByRole("button", { name: "Next" }));
    await screen.findByText("user11@example.com");

    await user.selectOptions(screen.getByLabelText("Rows per page"), "25");

    expect(await screen.findByText("user12@example.com")).toBeInTheDocument();
    expect(screen.getByText("Page 1")).toBeInTheDocument();
    expect(bodyRows()).toHaveLength(12);
  });

  it("mc12 shows and hides the schema", async () => {
    await openBrowser();
    await user.click(screen.getByRole("button", { name: "Show schema" }));
    expect(await screen.findByLabelText("Schema")).toHaveTextContent('"name": "users-model"');

    await user.click(screen.getByRole("button", { name: "Hide schema" }));
    expect(screen.queryByLabelText("Schema")).not.toBeInTheDocument();
  });

  it("mc17 an API error replaces the table with the message", async () => {
    await openBrowser();
    server.use(
      http.get("*/api/v1/data/:slug/", () =>
        HttpResponse.json({ trace_id: "error", message: "Entity model not found" }, { status: 400 }),
      ),
    );
    await user.selectOptions(screen.getByLabelText("Collection"), "user-permissions");

    expect(await screen.findByRole("alert")).toHaveTextContent("error: Entity model not found");
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("mc23 an empty page says so instead of showing an empty table", async () => {
    await openBrowser();
    server.use(
      http.get("*/api/v1/data/:slug/", () =>
        HttpResponse.json({ code: 0, data: [], page: 1, page_size: 10, total_page: 0, total_data: 0, message: "", data_schema: null }),
      ),
    );
    await user.selectOptions(screen.getByLabelText("Collection"), "user-permissions");

    expect(await screen.findByText("No rows on this page.")).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });
});
