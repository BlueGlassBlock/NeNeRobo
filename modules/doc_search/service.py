import asyncio
from concurrent.futures import ProcessPoolExecutor
from dataclasses import field
from pathlib import Path

from graia.saya import Channel
from httpx import AsyncClient
from kayaku import config, create
from launart import ExportInterface, Service
from launart.saya import LaunchableSchema
from loguru import logger
import aiosqlite
from aiosqlite import Connection
from zlib import adler32

channel = Channel.current()


class SearchInterface(ExportInterface):
    ...


DB = Path(__file__, "..", "objects.db").resolve()

DB.touch(exist_ok=True)


@config("search.sphinx")
class SphinxSearchConfig:
    """Configure Search of Sphinx"""

    inventory_urls: list[str] = field(default_factory=list)
    """Sphinx objects.inv urls."""

    domains: list[str] = field(default_factory=lambda: ["py"])
    """Acceptable domains."""


class SphinxSearchService(Service):
    id = "service.search.sphinx"
    supported_interface_types = {SearchInterface}
    connection: Connection

    @property
    def stages(self):
        return {"preparing", "cleanup"}

    @property
    def required(self):
        return set()

    def get_interface(self, _):
        return SearchInterface()

    async def update_objects_data(self, url: str, data: bytes) -> None:
        file_hash = adler32(data)
        rows = [
            q
            async for q in await self.connection.execute(
                "SELECT value FROM hashes WHERE uri = ?", (file_hash,)
            )
        ]
        if not rows:
            await self.connection.execute(
                "INSERT INTO hashes(uri, value) VALUES (?, ?)",
                (url, file_hash),
            )
        elif rows[0][0] == file_hash:
            logger.debug(f"{url}'s object data is already up to date, skipping")
            return
        logger.debug(f"Creating table for {url}")
        await self.connection.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS ? USING FTS5(name, domain, role, uri)",
            (url,),
        )
        # TODO
        logger.debug(f"Updating {url}'s file hash")
        await self.connection.execute(
            "UPDATE hashes SET value = ? WHERE uri = ?", (file_hash, url)
        )

    async def launch(self, _):
        async with self.stage("preparing"):
            conf = create(SphinxSearchConfig)
            self.connection = aiosqlite.connect(DB, isolation_level=None)
            await self.connection.__aenter__()
            await self.connection.execute(
                "CREATE TABLE IF NOT EXISTS hashes(uri PRIMARY KEY, value);"
            )
            await self.connection.execute(
                "CREATE VIRTUAL TABLE IF NOT EXISTS objects USING FTS5(name, domain, role, uri);"
            )
            async with AsyncClient() as client:
                for url in conf.inventory_urls:
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
            await self.connection.__aexit__(None, None, None)


channel.use(LaunchableSchema())(SphinxSearchService())
