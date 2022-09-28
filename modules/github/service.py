import asyncio
import base64
import shutil
from collections import deque
from pathlib import Path
from typing import Coroutine

from githubkit import GitHub as BaseGitHub
from githubkit import TokenAuthStrategy
from graia.saya import Channel
from kayaku import create
from launart import ExportInterface, Launart, Service
from launart.saya import LaunchableSchema
from loguru import logger
from rich.progress import Progress

channel = Channel.current()


class GitHub(BaseGitHub, ExportInterface):
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

    async def download_blob(self, owner: str, repo: str, sha: str, path: Path) -> None:
        git = self.instance.rest.git
        content_b64: str | None = None
        while content_b64 is None:
            try:
                content_b64 = (
                    await git.async_get_blob(owner, repo, sha)
                ).parsed_data.content
            except Exception as e:
                logger.error(repr(e))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(base64.b64decode(content_b64))
        logger.trace(f"Wrote file: {path.as_posix()}")

    async def download_tree(self, owner: str, repo: str, sha: str, base_path: Path):
        git = self.instance.rest.git
        files = [
            i
            for i in (
                await git.async_get_tree(owner, repo, sha, recursive="true")
            ).parsed_data.tree
            if i.type == "blob"
        ]
        logger.trace(f"Got directory info: {len(files)} files.")
        with Progress() as prog:
            tracker = prog.add_task("Downloading files...", total=len(files))
            dl_queue: deque[Coroutine] = deque(
                self.download_blob(owner, repo, f.sha, Path(base_path, f.path))
                for f in files
                if isinstance(f.sha, str) and isinstance(f.path, str)
            )
            tsk_deque: deque[asyncio.Task] = deque()
            while dl_queue or tsk_deque:
                while len(tsk_deque) < 8 and dl_queue:  # 8 connections for stability
                    tsk_deque.append(asyncio.create_task(dl_queue.pop()))
                while tsk_deque and tsk_deque[0].done():
                    tsk_deque.popleft()
                    prog.update(tracker, advance=1)
                await asyncio.sleep(0.5)

    async def download_templates(self):
        """Download templates.
        Source: https://github.com/cscs181/QQ-GitHub-Bot/tree/master/src/plugins/github/libs/renderer/templates
        """
        base_path = Path(__file__, "..", "templates").resolve()
        base_path.mkdir(parents=True, exist_ok=True)
        owner, repo = "cscs181", "QQ-GitHub-Bot"
        git = self.instance.rest.git
        # Fetch latest SHA
        commit_sha = (
            await git.async_get_ref(owner, repo, "heads/master")
        ).parsed_data.object_.sha
        if (commit_file := Path(base_path, "COMMIT")).exists():
            file_sha = commit_file.read_text(encoding="utf-8")
            if commit_sha == file_sha:
                logger.success(f"Already downloaded repository at Commit({file_sha}).")
                return
        # Fetch using git tree API
        segments = "src/plugins/github/libs/renderer/templates".split("/")
        data = (await git.async_get_tree(owner, repo, commit_sha)).parsed_data
        for seg in segments:
            for item in data.tree:
                if item.path == seg and isinstance(item.sha, str):
                    data = (await git.async_get_tree(owner, repo, item.sha)).parsed_data
                    break
        logger.trace("Fetched template git tree.")
        assert isinstance(data.sha, str)
        if (sha_file := Path(base_path, "TEMPLATE_SHA")).exists():
            file_sha = sha_file.read_text(encoding="utf-8")
            if data.sha == file_sha:
                logger.success(f"Already downloaded templates tree at SHA({file_sha}).")
                return
        logger.warning("Deleting template directory for a clean download.")
        shutil.rmtree(base_path)
        base_path.mkdir(parents=True, exist_ok=True)
        await self.download_tree(owner, repo, data.sha, base_path)
        Path(base_path, "TEMPLATE_SHA").write_text(data.sha, "utf-8")
        Path(base_path, "COMMIT").write_text(commit_sha, encoding="utf-8")
        logger.success(f"Wrote tree SHA: {data.sha}.")
        logger.success(f"Wrote commit SHA: {commit_file}.")

    async def launch(self, _):
        from . import Credential

        async with self.stage("preparing"):
            # Download templates on call
            self.instance = GitHub(auth=TokenAuthStrategy(create(Credential).token))
            await self.instance.__aenter__()
            logger.info(
                "Downloading GitHub render templates...",
                alt="[orange]Downloading GitHub render templates...",
            )
            await self.download_templates()
            logger.success(
                "Downloaded GitHub render templates.",
                alt="[green]Downloading GitHub render templates.",
            )

        async with self.stage("cleanup"):
            await self.instance.__aexit__()


channel.use(LaunchableSchema())(GitHubService())
