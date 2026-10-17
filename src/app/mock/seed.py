"""Insert mock users and permissions. Safe to run twice: existing emails are skipped.

python -m app.mock.seed --yes
"""

import argparse
import sys

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.config import Settings
from app.domain.models.user import Base, UserPermissionModel
from app.interface.repositories.postgres_user import PostgresUserRepository
from app.mock.data import EXTRA_ADMIN_PERMISSIONS, MOCK_PASSWORD, MOCK_USERS
from app.shared.security import hash_password


def seed(session: Session) -> dict[str, int]:
    repo = PostgresUserRepository(session)
    created_users = 0
    created_permissions = 0
    password_hash = hash_password(MOCK_PASSWORD)

    for mock in MOCK_USERS:
        if repo.get_by_email(mock.email) is not None:
            continue
        user = repo.insert_user(mock.email, password_hash, mock.first_name, mock.last_name)
        created_users += 1
        permissions = [mock.permission] if mock.permission else []
        if mock.permission == "admin":
            permissions += EXTRA_ADMIN_PERMISSIONS
        for permission in permissions:
            session.add(UserPermissionModel(user_id=user.id, permission=permission))
            created_permissions += 1
        session.commit()
    return {"users": created_users, "permissions": created_permissions}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--yes", action="store_true", help="confirm writing mock data")
    args = parser.parse_args(argv)

    settings = Settings()
    target = (
        f"{settings.goapp_postgres_db_host}:{settings.goapp_postgres_db_port}"
        f"/{settings.goapp_postgres_db_name}"
    )
    print(f"Target database: {target}")
    if not args.yes:
        print("Mock users all share a known password. Re-run with --yes to continue.")
        return 2

    engine = create_engine(settings.postgres_url)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        result = seed(session)
    print(f"Seeded {result['users']} users, {result['permissions']} permissions")
    print(f"Mock password for every user: {MOCK_PASSWORD}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
