import { useAuth } from "../context/auth_context";

export function Profile() {
  const { user } = useAuth();
  if (!user) return null;

  return (
    <section className="card" aria-labelledby="profile-title">
      <h2 id="profile-title">Profile</h2>
      <dl className="facts">
        <dt>Name</dt>
        <dd>{`${user.first_name} ${user.last_name}`.trim() || "—"}</dd>
        <dt>Email</dt>
        <dd>{user.email}</dd>
        <dt>User id</dt>
        <dd>{user.id}</dd>
      </dl>
    </section>
  );
}
