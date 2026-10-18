import pytest

from app.domain.errors import ConflictError
from app.domain.models.user import UserPermissionModel
from app.interface.repositories.postgres_user import PostgresUserRepository


@pytest.fixture
def repo(session):
    return PostgresUserRepository(session)


def make_user(repo, email="a@b.co"):
    return repo.insert_user(email, "hash", "Ann", "Lee")


def test_insert_and_get(repo):
    user = make_user(repo)
    assert user.id is not None
    assert user.created_at is not None
    assert repo.get_by_email("a@b.co").id == user.id
    assert repo.get_by_id(user.id).email == "a@b.co"
    assert repo.get_by_email("missing@b.co") is None


def test_duplicate_email_raises_conflict(repo):
    make_user(repo)
    with pytest.raises(ConflictError):
        make_user(repo)
    # session must still be usable after the failed insert
    assert make_user(repo, "other@b.co").id is not None


def test_upsert_token_keeps_one_row_per_user(repo):
    user = make_user(repo)
    repo.upsert_token(user.id, "a1", "r1")
    repo.upsert_token(user.id, "a2", "r2")
    row = repo.find_token_by_user(user.id)
    assert (row.access, row.refresh) == ("a2", "r2")
    assert repo.find_token_by_user_and_access(user.id, "a1") is None
    assert repo.find_token_by_user_and_access(user.id, "a2") is not None


def test_delete_token(repo):
    user = make_user(repo)
    repo.upsert_token(user.id, "a", "r")
    repo.delete_token(user.id)
    assert repo.find_token_by_user(user.id) is None


def test_get_permission(repo, session):
    user = make_user(repo)
    assert repo.get_permission(user.id) is None
    session.add(UserPermissionModel(user_id=user.id, permission="admin"))
    session.commit()
    assert repo.get_permission(user.id).permission == "admin"
