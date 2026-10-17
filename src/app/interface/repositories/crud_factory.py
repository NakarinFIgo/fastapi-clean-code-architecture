from pymongo.database import Database
from sqlalchemy.orm import Session

from app.domain.entities.crud import CrudResource, Datasource
from app.domain.errors import NotFoundError
from app.domain.repositories.crud import ICrudRepository
from app.interface.repositories.mongo_crud import MongoCrudRepository
from app.interface.repositories.postgres_crud import PostgresCrudRepository


class CrudRepositoryFactory:
    def __init__(
        self,
        resources: list[CrudResource],
        session: Session,
        mongo_db: Database | None = None,  # type: ignore[type-arg]
    ) -> None:
        self._by_slug = {r.slug: r for r in resources}
        self._session = session
        self._mongo_db = mongo_db

    def get(self, slug: str) -> ICrudRepository:
        resource = self._by_slug.get(slug)
        if resource is None:
            raise NotFoundError("Entity model not found")
        if resource.datasource is Datasource.POSTGRESQL:
            return PostgresCrudRepository(resource, self._session)
        if resource.datasource is Datasource.MONGODB and self._mongo_db is not None:
            return MongoCrudRepository(resource, self._mongo_db[resource.name])
        raise NotFoundError("Datasource not supported")
