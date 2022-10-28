from dataclasses import field
import secrets
from typing import Annotated

from graia.amnesia.builtins.aiohttp import AiohttpClientInterface
from graia.ariadne.app import Ariadne
from graia.ariadne.event.message import FriendMessage, GroupMessage
from graia.ariadne.message.element import Image
from graia.ariadne.message.exp import MessageChain
from graia.ariadne.message.parser.base import MatchRegex, RegexGroup
from graia.saya import Channel
from graia.saya.builtins.broadcast import ListenerSchema
from graia.scheduler.saya import SchedulerSchema
from graia.scheduler.timers import every_custom_seconds
from kayaku import config, create
from loguru import logger

from .render import format_event, link_to_image
from .service import GitHub

channel = Channel.current()


@config("github.credential")
class MasterCredential:
    client_id: str
    """OAuth Device Client ID, for users to authenticate and act on their behalf."""
    token: str
    """Personal Access Token, for basic fetch and poll task."""


@config("github.orgs.monitor")
class OrgMonitor:
    orgs: list[str] = field(default_factory=list)
    """Set of Organizations that you want to monitor."""
    groups: list[int] = field(default_factory=list)
    """Target groups"""


@channel.use(
    ListenerSchema(
        [GroupMessage, FriendMessage],
        inline_dispatchers=[
            MatchRegex(
                r"((https?://)?github\.com/)?(?P<owner>[^/]+)/(?P<repo>[^/]+)/(issues|pull)/(?P<number>\d+)",
                full=True,
            )
        ],
    )
)
@channel.use(
    ListenerSchema(
        [GroupMessage, FriendMessage],
        inline_dispatchers=[
            MatchRegex(r"(?P<owner>[^/]+)/(?P<repo>[^/]+)#(?P<number>\d+)", full=True),
        ],
    )
)
async def render_link(
    app: Ariadne,
    ev: GroupMessage | FriendMessage,
    owner_chain: Annotated[MessageChain, RegexGroup("owner")],
    repo_chain: Annotated[MessageChain, RegexGroup("repo")],
    issue_number: Annotated[MessageChain, RegexGroup("number")],
    gh: GitHub,
):
    owner, repo, number = owner_chain.display, repo_chain.display, issue_number.display
    try:
        await gh.rest.issues.async_get(owner, repo, int(number))
    except Exception as e:
        return await app.send_message(ev, f"验证 Issue 失败：{repr(e)}", quote=ev.source)
    try:
        return await app.send_message(
            ev,
            Image(
                data_bytes=await link_to_image(
                    f"https://github.com/{owner}/{repo}/issues/{number}"
                )
            ),
            quote=ev.source,
        )
    except TimeoutError:
        return await app.send_message(ev, "Timeout in 80000ms!", quote=ev.source)


@channel.use(
    ListenerSchema(
        [GroupMessage, FriendMessage],
        inline_dispatchers=[
            MatchRegex(
                r"((https?://)?github\.com/)?(?P<owner>[^/]+)/(?P<repo>[^/]+)",
                full=True,
            )
        ],
    )
)
async def render_open_graph(
    app: Ariadne,
    ev: GroupMessage | FriendMessage,
    owner_chain: Annotated[MessageChain, RegexGroup("owner")],
    repo_chain: Annotated[MessageChain, RegexGroup("repo")],
    client: AiohttpClientInterface,
):
    owner, repo = owner_chain.display, repo_chain.display
    try:
        pic = (
            await (
                await client.request(
                    "get",
                    f"https://opengraph.githubassets.com/{secrets.token_urlsafe(16)}/"
                    f"{owner}/{repo}",
                )
            )
            .io()
            .read()
        )
        return await app.send_message(ev, Image(data_bytes=pic))
    except Exception as e:
        return await app.send_message(ev, f"拉取 OpenGraph 失败：{repr(e)}", quote=ev.source)


@channel.use(SchedulerSchema(every_custom_seconds(5)))
async def update_stat(app: Ariadne):
    gh = app.launch_manager.get_interface(GitHub)
    groups: list[int] = create(OrgMonitor).groups
    for events in gh.polls.values():
        while events and (ev := events.popleft()):
            # TODO: Render events
            logger.debug(repr(ev))
            if formatted := format_event(ev):
                for g in groups:
                    await app.send_group_message(g, formatted)
