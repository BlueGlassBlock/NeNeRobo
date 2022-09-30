from typing import TypeVar

from githubkit import BaseAuthStrategy
from githubkit import GitHub as BaseGitHub
from githubkit import OAuthAppAuthStrategy
from graia.saya import Channel
from kayaku import create
from launart import ExportInterface, Service
from launart.saya import LaunchableSchema
from loguru import logger

channel = Channel.current()

A = TypeVar("A", bound=BaseAuthStrategy)


class GitHub(BaseGitHub[A], ExportInterface):
    ...


class GitHubService(Service):
    id = "service.github"
    instance: GitHub
    supported_interface_types = {GitHub}

    @property
    def stages(self):
        return {"preparing", "cleanup"}

    @property
    def required(self):
        return set()

    def get_interface(self, _: type[GitHub]) -> GitHub:
        return self.instance

    async def launch(self, _):
        from . import Credential

        async with self.stage("preparing"):
            credential = create(Credential)
            self.instance = GitHub(
                auth=OAuthAppAuthStrategy(credential.client_id, credential.client_id)
            )
            logger.info(f"Using auth strategy: {self.instance.auth.__class__.__name__}")
            await self.instance.__aenter__()

        async with self.stage("cleanup"):
            await self.instance.__aexit__()


channel.use(LaunchableSchema())(GitHubService())
