import { AuthProvider, useAuth } from "./auth/AuthContext";
import { DataBrowser } from "./components/DataBrowser";
import { LoginRegister } from "./components/LoginRegister";
import { Profile } from "./components/Profile";

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
