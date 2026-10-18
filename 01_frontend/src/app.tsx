import { AuthProvider, useAuth } from "./features/auth/context/auth_context";
import { DataBrowser } from "./features/data_browser/component/data_browser";
import { LoginRegister } from "./features/auth/component/login_register";
import { Profile } from "./features/auth/component/profile";

function Shell() {
  const { user, restoring, logout } = useAuth();

  return (
    <>
      <header className="topbar">
        <h1>Clean Architecture Console</h1>
        {user && (
          <button type="button" className="ghost" onClick={logout}>
            Log out
          </button>
        )}
      </header>
      <main>
        {restoring ? (
          <p aria-live="polite">Checking your session…</p>
        ) : user ? (
          <>
            <Profile />
            <DataBrowser />
          </>
        ) : (
          <LoginRegister />
        )}
      </main>
    </>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <Shell />
    </AuthProvider>
  );
}
