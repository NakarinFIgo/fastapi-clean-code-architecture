import { useState } from "react";
import type { FormEvent } from "react";

import { ApiError } from "../../../shared/api/client";
import { register } from "../api/auth_service";
import { useAuth } from "../context/auth_context";

type Mode = "login" | "register";

export function LoginRegister() {
  const { login, expired } = useAuth();
  const [mode, setMode] = useState<Mode>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setNotice(null);
    setBusy(true);
    try {
      if (mode === "login") {
        await login(email, password);
      } else {
        await register({ email, password, first_name: firstName, last_name: lastName });
        setNotice("Registered. You can log in now.");
        setMode("login");
        setPassword("");
      }
    } catch (e) {
      setError(e instanceof ApiError ? e.display : "Something went wrong");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="card narrow" aria-labelledby="auth-title">
      <div className="tabs" role="tablist">
        {(["login", "register"] as const).map((m) => (
          <button
            key={m}
            type="button"
            role="tab"
            aria-selected={mode === m}
            className={mode === m ? "tab active" : "tab"}
            onClick={() => {
              setMode(m);
              setError(null);
            }}
          >
            {m === "login" ? "Log in" : "Register"}
          </button>
        ))}
      </div>
      <h2 id="auth-title">{mode === "login" ? "Welcome back" : "Create an account"}</h2>

      {expired && mode === "login" && (
        <p className="banner warning" role="status">
          Your session expired. Please log in again.
        </p>
      )}
      {notice && (
        <p className="banner success" role="status">
          {notice}
        </p>
      )}

      <form onSubmit={onSubmit}>
        <label>
          Email
          <input type="text" autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} />
        </label>
        <label>
          Password
          <input
            type="password"
            autoComplete={mode === "login" ? "current-password" : "new-password"}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </label>
        {mode === "register" && (
          <>
            <label>
              First name
              <input type="text" value={firstName} onChange={(e) => setFirstName(e.target.value)} />
            </label>
            <label>
              Last name
              <input type="text" value={lastName} onChange={(e) => setLastName(e.target.value)} />
            </label>
          </>
        )}
        {error && (
          <p className="banner error" role="alert">
            {error}
          </p>
        )}
        <button type="submit" className="primary" disabled={busy}>
          {busy ? "Please wait…" : mode === "login" ? "Log in" : "Register"}
        </button>
      </form>
    </section>
  );
}
