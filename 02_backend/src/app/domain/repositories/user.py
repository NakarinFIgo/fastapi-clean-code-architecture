from abc import ABC, abstractmethod

from app.domain.models.user import UserModel, UserPermissionModel, UserTokenModel


class IUserRepository(ABC):
    @abstractmethod
    def insert_user(
        self, email: str, password_hash: str, first_name: str, last_name: str
    ) -> UserModel: ...

    @abstractmethod
    def get_by_email(self, email: str) -> UserModel | None: ...

    @abstractmethod
    def get_by_id(self, user_id: int) -> UserModel | None: ...

    @abstractmethod
    def upsert_token(self, user_id: int, access: str, refresh: str) -> None: ...

    @abstractmethod
    def find_token_by_user(self, user_id: int) -> UserTokenModel | None: ...

    @abstractmethod
    def find_token_by_user_and_access(self, user_id: int, access: str) -> UserTokenModel | None: ...

    @abstractmethod
    def delete_token(self, user_id: int) -> None: ...

    @abstractmethod
    def get_permission(self, user_id: int) -> UserPermissionModel | None: ...
