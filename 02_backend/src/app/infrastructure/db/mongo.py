from pymongo import MongoClient
from pymongo.database import Database


def build_mongo_database(uri: str, name: str) -> Database | None:  # type: ignore[type-arg]
    if not uri:
        return None
    return MongoClient(uri)[name]  # MongoClient connects lazily
