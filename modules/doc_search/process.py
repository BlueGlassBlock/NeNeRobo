from typing import TypedDict

from loguru import logger
from msgspec import Struct
from sphobjinv import Inventory


class EntryTypedDict(TypedDict):
    name: str
    domain: str
    role: str
    priority: str
    uri: str
    dispname: str


class Entry(Struct):
    name: str
    domain: str
    role: str
    uri: str


Database = dict[str, dict[str, list[Entry]]]


def parse_object(url: str, data: bytes, domains: list[str]) -> Database:
    inv = Inventory(zlib=data)  # type: ignore
    json_obj = inv.json_dict(expand=True)
    json_obj.pop("project")
    json_obj.pop("version")
    json_obj.pop("count")
    json_obj.pop("metadata", None)
    db: Database = {}
    for entry in json_obj.values():
        entry: EntryTypedDict
        if entry["domain"] not in domains:
            continue
        db.setdefault(entry["domain"], {}).setdefault(entry["role"], []).append(
            Entry(entry["name"], entry["domain"], entry["role"], url + entry["uri"])
        )
    return db
