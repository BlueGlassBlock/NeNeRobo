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

channel = Channel.current()
from yarl import URL

from .process import Database, parse_object


class SearchInterface(ExportInterface):
    ...


HASH_DB = Path(__file__, "..", "hash.db")
DB = Path(__file__, "..", "objects.db")


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

    @property
    def stages(self):
        return {"preparing"}

    @property
    def required(self):
        return set()

    def get_interface(self, _):
        return SearchInterface()

    async def launch(self, _):
        loop = asyncio.get_running_loop()
        proc_exec = ProcessPoolExecutor(max_workers=4)
        async with self.stage("preparing"):
            conf = create(SphinxSearchConfig)
            async with AsyncClient() as client:
                futures: list[asyncio.Future[Database]] = []
                for url in conf.inventory_urls:
                    data = (await client.get(url)).content
                    logger.debug(f"Fetched objects.inv from {url}")
                    futures.append(
                        loop.run_in_executor(
                            proc_exec,
                            parse_object,
                            f"{str(URL(url).parent)}/",
                            data,
                            conf.domains,
                        )
                    )

                if not futures:
                    return logger.warning("No objects.inv url specified!")
                await asyncio.wait(futures)


channel.use(LaunchableSchema())(SphinxSearchService())
