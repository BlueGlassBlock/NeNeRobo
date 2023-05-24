import asyncio
from sphobjinv.inventory import Inventory
from dataclasses import field
from pathlib import Path

from graia.saya import Channel
from httpx import AsyncClient
from kayaku import config, create
from launart import ExportInterface, Service
from launart.saya import LaunchableSchema
from loguru import logger
from yarl import URL
import aiosqlite
from aiosqlite import Connection
from zlib import adler32
from sphobjinv.zlib import decompress as sph_decompress
from rich.progress import Progress, SpinnerColumn, MofNCompleteColumn, TimeElapsedColumn
from dataclasses import dataclass

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


DB = Path(__file__, "..", "objects.db").resolve()

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

    async def write_table(self, url: str, inv: Inventory) -> None:
        head_uri = f"{str(URL(url).parent)}/"
        logger.info(f"Traversing {len(inv.objects)} entries of {url}")
        tasks: list[asyncio.Task] = []
        for d in inv.objects:
            dct = d.json_dict(expand=True)
            dct["uri"] = head_uri + dct["uri"]
            if dct["domain"] in self.config.domains:
                tsk = asyncio.create_task(
                    self.connection.execute(
                        f"INSERT INTO {url!r} VALUES (:name, :domain, :role, :uri);",
                        dct,
                    )
                )
                tasks.append(tsk)

        with Progress(
            SpinnerColumn(),
            *Progress.get_default_columns(),
            TimeElapsedColumn(),
            MofNCompleteColumn(),
        ) as prog:
            tid = prog.add_task(
                f"[cyan]Writing {len(tasks)} entries into database[/]", total=len(tasks)
            )
            for t in tasks:
                t.add_done_callback(lambda _: prog.advance(tid))
            await asyncio.wait(tasks)

    async def update_objects_data(self, url: str, data: bytes) -> None:
        file_hash = adler32(data)
        rows = list(
            await (
                await self.connection.execute(
                    "SELECT * FROM hashes WHERE uri = ?;", (url,)
                )
            ).fetchall()
        )
        if not rows:
            await self.connection.execute(
                "INSERT INTO hashes(uri, value) VALUES (?, ?);",
                (url, -1),
            )
        elif rows[0][1] == file_hash:
            logger.debug(f"{url}'s object data is already up to date, skipping")
            return
        logger.debug(f"Remove and recreate table {url}")
        await self.connection.execute(f"DROP TABLE IF EXISTS {url!r};")
        await self.connection.execute(
            f"CREATE VIRTUAL TABLE {url!r} USING FTS5(name, domain UNINDEXED, role UNINDEXED, uri UNINDEXED);"
        )
        inv = Inventory(sph_decompress(data))  # type: ignore
        await self.write_table(url, inv)
        logger.debug(f"Updating {url}'s file hash")
        await self.connection.execute(
            "REPLACE INTO hashes VALUES(?, ?)",
            (url, file_hash),
        )

    async def launch(self, _):
        async with aiosqlite.connect(DB, isolation_level=None) as connection:
            self.connection = connection
            async with self.stage("preparing"):
                self.config = conf = create(SphinxSearchConfig)
                await self.connection.execute(
                    "CREATE TABLE IF NOT EXISTS hashes(uri PRIMARY KEY, value);"
                )
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
                        await self.update_objects_data(url, data)

            async with self.stage("cleanup"):
                ...


channel.use(LaunchableSchema())(SphinxSearchService())
