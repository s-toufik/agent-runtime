from typing import Any

from pymongo.errors import OperationFailure

INDEX_OPTIONS_CONFLICT: int = 85


class FakeAdmin:
    def command(self, name: str) -> dict[str, Any]:
        return {"ok": 1.0}


class FakeCollection:
    def __init__(self, database: FakeDatabase, name: str) -> None:
        self.database = database
        self.name = name
        self.indexes: list[dict[str, Any]] = [{"key": {"_id": 1}, "name": "_id_"}]

    def list_indexes(self) -> list[dict[str, Any]]:
        return [dict(index) for index in self.indexes]

    def create_index(self, keys: list[tuple[str, int]], **options: Any) -> str:
        key = dict(keys)
        name = "_".join(f"{field}_{order}" for field, order in keys)
        for index in self.indexes:
            if index["key"] == key:
                if index.get("expireAfterSeconds") != options.get("expireAfterSeconds"):
                    raise OperationFailure(
                        "An equivalent index already exists with the same name but different options",
                        INDEX_OPTIONS_CONFLICT,
                    )
                return name
        self.indexes.append({"key": key, "name": name, **options})
        return name

    def ttl(self) -> int | None:
        for index in self.indexes:
            if index["key"] == {"created_at": 1}:
                return index.get("expireAfterSeconds")
        return None


class FakeDatabase:
    def __init__(self, name: str) -> None:
        self.name = name
        self.collections: dict[str, FakeCollection] = {}

    def __getitem__(self, name: str) -> FakeCollection:
        return self.collections.setdefault(name, FakeCollection(self, name))

    def command(self, command: str, name: str, **options: Any) -> dict[str, Any]:
        change = options["index"]
        for index in self[name].indexes:
            if index["key"] == change["keyPattern"]:
                index["expireAfterSeconds"] = change["expireAfterSeconds"]
        return {"ok": 1.0}


class FakeMongoClient:
    """Answers ping and keeps indexes; refuses an index again with another TTL, as MongoDB does."""

    def __init__(self) -> None:
        self.admin = FakeAdmin()
        self.databases: dict[str, FakeDatabase] = {}

    def __getitem__(self, name: str) -> FakeDatabase:
        return self.databases.setdefault(name, FakeDatabase(name))

    def close(self) -> None:
        pass
