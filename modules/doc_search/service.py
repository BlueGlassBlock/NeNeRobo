import asyncio
from dataclasses import dataclass, field
import sqlite3
from zlib import adler32

import aiosqlite
from aiosqlite import Connection
from graia.saya import Channel
from httpx import AsyncClient
from kayaku import config, create
from launart import ExportInterface, Service
from launart.saya import LaunchableSchema
from loguru import logger
from rich.progress import MofNCompleteColumn, Progress, SpinnerColumn, TimeElapsedColumn
from sphobjinv.inventory import Inventory
from sphobjinv.zlib import decompress as sph_decompress
from yarl import URL

from library.storage import dir

channel = Channel.current()


@dataclass(frozen=True, eq=True)
class SearchResult:
    rank: float  # lower is better
    role: str
    name: str
    uri: str


class SearchInterface(ExportInterface):
    service: "SphinxSearchService"

    def __init__(self, service: "SphinxSearchService") -> None:
        self.service = service
        self.conn = self.service.connection

    async def search(self, query: str, total: int):
        results: list[SearchResult] = []
        for db_name_js in self.service.config.inventory_urls:
            async for row in await self.conn.execute(
                f"SELECT rank, role, name, uri FROM {str(db_name_js)!r}(?)"
                f" ORDER BY rank LIMIT ?;",
                (query, total),
            ):
                results.append(SearchResult(*row))
        results.sort(key=lambda r: r.rank)
        return results[:total]


DB = dir("doc_search") / "objects.db"
DB.touch(exist_ok=True)


@config("search.sphinx")
class SphinxSearchConfig:
    """Configure Search of Sphinx"""

    inventory_urls: list[str] = field(default_factory=list)
    """Sphinx objects.inv urls."""

    domains: list[str] = field(default_factory=lambda: ["py"])
    """Acceptable domains."""

    command: str = "[#search|#搜|搜文档] {...phrase:raw}"


class SphinxSearchService(Service):
    id = "service.search.sphinx"
    supported_interface_types = {SearchInterface}
    connection: Connection
    config: SphinxSearchConfig

    @property
    def stages(self):
        return {"preparing", "cleanup"}

    @property
    def required(self):
        return {"ichika.main"}

    def get_interface(self, _):
        return SearchInterface(self)

    def write_table(self, conn: sqlite3.Connection, url: str, inv: Inventory) -> None:
        head_uri = f"{str(URL(url).parent)}/"
        logger.info(f"Traversing {len(inv.objects)} entries of {url}")
        with Progress(
            SpinnerColumn(),
            *Progress.get_default_columns(),
            TimeElapsedColumn(),
            MofNCompleteColumn(),
        ) as prog:
            tid = prog.add_task(
                f"[cyan]Writing {len(inv.objects)} entries into database[/]",
                total=len(inv.objects),
            )
            for d in inv.objects:
                dct = d.json_dict(expand=True)
                dct["uri"] = head_uri + dct["uri"]
                if dct["domain"] in self.config.domains:
                    conn.execute(
                        f"INSERT INTO {url!r} VALUES (:name, :domain, :role, :uri);",
                        dct,
                    )
                prog.advance(tid)

    def update_objects_data(
        self, conn: sqlite3.Connection, url: str, data: bytes
    ) -> None:
        file_hash = adler32(data)
        rows = list(
            conn.execute("SELECT * FROM hashes WHERE uri = ?;", (url,)).fetchall()
        )
        if not rows:
            conn.execute(
                "INSERT INTO hashes(uri, value) VALUES (?, ?);",
                (url, -1),
            )
        elif rows[0][1] == file_hash:
            logger.debug(f"{url}'s object data is already up to date, skipping")
            return
        logger.debug(f"Remove and recreate table {url}")
        conn.execute(f"DROP TABLE IF EXISTS {url!r};")
        conn.execute(
            f"CREATE VIRTUAL TABLE {url!r} USING FTS5(name, domain UNINDEXED, role UNINDEXED, uri UNINDEXED);"
        )
        inv = Inventory(sph_decompress(data))  # type: ignore
        self.write_table(conn, url, inv)
        logger.debug(f"Updating {url}'s file hash")
        conn.execute(
            "REPLACE INTO hashes VALUES(?, ?)",
            (url, file_hash),
        )

    async def launch(self, _):
        async with self.stage("preparing"):
            self.config = conf = create(SphinxSearchConfig)
            conn = sqlite3.connect(DB, isolation_level=None)
            conn.execute("CREATE TABLE IF NOT EXISTS hashes(uri PRIMARY KEY, value);")
            conn.execute("CREATE TABLE IF NOT EXISTS hashes(uri PRIMARY KEY, value);")
            data_map: dict[str, bytes] = {}
            async with AsyncClient() as client:
                for url in conf.inventory_urls:
                    url = str(url)  # Convert JString
                    data = None
                    while data is None:
                        try:
                            data = (await client.get(url)).content
                        except Exception as e:
                            logger.error(f"Error fetching {url}: {e!r}, retrying")
                            await asyncio.sleep(0.5)
                    logger.debug(f"Fetched objects.inv from {url}")
                    data_map[url] = data
            for url, data in data_map.items():
                self.update_objects_data(conn, url, data)
            conn.close()

            self.connection_mgr = aiosqlite.connect(DB, isolation_level=None)
            self.connection = await self.connection_mgr.__aenter__()

        async with self.stage("cleanup"):
            await self.connection_mgr.__aexit__(None, None, None)


channel.use(LaunchableSchema())(SphinxSearchService())
