import asyncio
import contextlib
import datetime as dt_mod
from asyncio import Task
from collections import deque
from datetime import datetime, timedelta
from operator import attrgetter

from githubkit import GitHub as BaseGitHub
from githubkit import TokenAuthStrategy
from githubkit.exception import GitHubException
from githubkit.rest.models import Event
from graia.saya import Channel
from kayaku import create
from launart import ExportInterface, Service
from launart.saya import LaunchableSchema
from loguru import logger

channel = Channel.current()


class GitHub(BaseGitHub[TokenAuthStrategy], ExportInterface):
    def __init__(
        self, auth: TokenAuthStrategy, polls: dict[str, deque[Event]] | None = None
    ):
        super().__init__(auth)
        self.polls: dict[str, deque[Event]] = polls if polls is not None else {}


class GitHubService(Service):
    id = "service.github"
    instance: GitHub
    polls: dict[str, deque[Event]]
    tasks: set[Task]
    supported_interface_types = {GitHub}

    @property
    def stages(self):
        return {"preparing", "cleanup"}

    @property
    def required(self):
        return set()

    def get_interface(self, _: type[GitHub]) -> GitHub:
        return self.instance

    @logger.catch
    async def poll_org(self, org: str, update_deque: deque[Event]) -> None:
        last_poll = datetime.now(tz=dt_mod.timezone(timedelta(hours=8)))  # UTC+8
        inst = GitHub(self.instance.auth)
        poll_func = inst.rest.activity.async_list_public_org_events
        async with inst:
            async with inst.get_async_client() as client:
                while True:
                    try:
                        resp = await poll_func(org)
                        if resp.status_code == 200:  # New event arrived
                            update_deque.extend(
                                sorted(
                                    (
                                        e
                                        for e in resp.parsed_data
                                        if e.created_at and e.created_at > last_poll
                                    ),
                                    key=attrgetter("created_at"),
                                )
                            )
                        if resp.status_code in (200, 304):
                            client.headers["If-None-Match"] = resp.headers["ETag"]
                            last_poll = datetime.now(
                                tz=dt_mod.timezone(timedelta(hours=8))  # UTC+8
                            )
                        await asyncio.sleep(
                            float(resp.headers.get("X-Poll-Interval", 30))
                        )
                    except GitHubException as e:
                        logger.error(f"Error polling {org}: {e!r}")

    async def launch(self, _):
        self.polls = {}
        self.tasks = set()
        from . import Credential, OrgMonitor

        async with self.stage("preparing"):
            credential = create(Credential)
            self.instance = GitHub(
                auth=TokenAuthStrategy(credential.token), polls=self.polls
            )
            logger.info(f"Using auth strategy: {self.instance.auth.__class__.__name__}")
            await self.instance.__aenter__()
            org_monitor = create(OrgMonitor)
            for org in org_monitor.orgs:
                self.polls[org] = deque()
                self.tasks.add(asyncio.create_task(self.poll_org(org, self.polls[org])))
                logger.info(f"Starting poll task for organization {org}")

        async with self.stage("cleanup"):
            for task in self.tasks:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
            await self.instance.__aexit__()


channel.use(LaunchableSchema())(GitHubService())
