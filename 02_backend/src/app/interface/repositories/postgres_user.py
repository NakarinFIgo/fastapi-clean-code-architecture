from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.errors import ConflictError
from app.domain.models.user import UserModel, UserPermissionModel, UserTokenModel
from app.domain.repositories.user import IUserRepository


class PostgresUserRepository(IUserRepository):
    def __init__(self, session: Session) -> None:
        self._s = session

    def insert_user(
        self, email: str, password_hash: str, first_name: str, last_name: str
    ) -> UserModel:
        user = UserModel(
            email=email, password=password_hash, first_name=first_name, last_name=last_name
        )
        self._s.add(user)
        try:
            self._s.commit()
        except IntegrityError as exc:
            self._s.rollback()
            raise ConflictError("email already registered") from exc
        return user

    def get_by_email(self, email: str) -> UserModel | None:
        return self._s.scalar(select(UserModel).where(UserModel.email == email))

    def get_by_id(self, user_id: int) -> UserModel | None:
        return self._s.get(UserModel, user_id)

    def upsert_token(self, user_id: int, access: str, refresh: str) -> None:
        row = self.find_token_by_user(user_id)
        if row is None:
            row = UserTokenModel(user_id=user_id)
            self._s.add(row)
        row.access = access
        row.refresh = refresh
        self._s.commit()

    def find_token_by_user(self, user_id: int) -> UserTokenModel | None:
        return self._s.scalar(select(UserTokenModel).where(UserTokenModel.user_id == user_id))

    def find_token_by_user_and_access(self, user_id: int, access: str) -> UserTokenModel | None:
        return self._s.scalar(
            select(UserTokenModel).where(
                UserTokenModel.user_id == user_id, UserTokenModel.access == access
            )
        )

    def delete_token(self, user_id: int) -> None:
        self._s.execute(delete(UserTokenModel).where(UserTokenModel.user_id == user_id))
        self._s.commit()

    def get_permission(self, user_id: int) -> UserPermissionModel | None:
        return self._s.scalar(
            select(UserPermissionModel).where(UserPermissionModel.user_id == user_id)
        )
