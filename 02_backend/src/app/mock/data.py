"""Mock data shared by the seed script and the tests (single source of truth)."""

from dataclasses import dataclass

# Every mock user has this password. Never seed these users into a shared or production DB.
MOCK_PASSWORD = "Passw0rd!"


@dataclass(frozen=True)
class MockUser:
    email: str
    first_name: str
    last_name: str
    permission: str | None  # None = no user_permissions row at all


ADMIN = MockUser("admin@example.com", "Admin", "User", "admin")
VIEWER = MockUser("viewer@example.com", "View", "Only", "viewer")
NO_PERMISSION = MockUser("nopermission@example.com", "No", "Permission", None)

MOCK_USERS: list[MockUser] = [ADMIN, VIEWER, NO_PERMISSION]

# Extra permission rows for the admin so the data browser has something to paginate:
# With the viewer's row that makes 27 rows in user_permissions.
EXTRA_ADMIN_PERMISSIONS: list[str] = [f"report:{i:02d}" for i in range(1, 26)]
