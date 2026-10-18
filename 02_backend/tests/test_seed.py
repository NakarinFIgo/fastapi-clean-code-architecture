from sqlalchemy import func, select

from app.domain.models.user import UserModel, UserPermissionModel
from app.mock.data import EXTRA_ADMIN_PERMISSIONS, MOCK_PASSWORD, MOCK_USERS
from app.mock.seed import main, seed
from app.shared.security import verify_password


def count(session, model) -> int:
    return session.scalar(select(func.count()).select_from(model)) or 0


def test_seed_creates_users_and_permissions(session):
    result = seed(session)

    assert result == {"users": len(MOCK_USERS), "permissions": 2 + len(EXTRA_ADMIN_PERMISSIONS)}
    assert count(session, UserModel) == len(MOCK_USERS)
    assert count(session, UserPermissionModel) == 2 + len(EXTRA_ADMIN_PERMISSIONS)
    admin = session.scalar(select(UserModel).where(UserModel.email == "admin@example.com"))
    assert verify_password(MOCK_PASSWORD, admin.password)


def test_seed_is_idempotent(session):
    seed(session)
    again = seed(session)

    assert again == {"users": 0, "permissions": 0}
    assert count(session, UserModel) == len(MOCK_USERS)


def test_seed_cli_refuses_without_yes(monkeypatch, capsys):
    monkeypatch.setenv("GOAPP_SECRET_KEY", "k")

    assert main([]) == 2
    out = capsys.readouterr().out
    assert "Target database:" in out
    assert "--yes" in out
