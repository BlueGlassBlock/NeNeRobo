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
from graia.scheduler.timers import every_minute
from kayaku import ConfigModel
from launart import Launart

from .render import link_to_image
from .service import GitHub

channel = Channel.current()


class Credential(ConfigModel, domain="github.credential"):
    client_id: str
    """OAuth Client ID"""
    client_secret: str
    """OAuth Client Secret"""


@channel.use(
    ListenerSchema(
        [GroupMessage, FriendMessage],
        inline_dispatchers=[
            MatchRegex(
                r"((https?://)?github\.com/)?(?P<owner>[^/]+)/(?P<repo>[^/]+)/(issues|pull)/(?P<number>\d+)"
            )
        ],
    )
)
@channel.use(
    ListenerSchema(
        [GroupMessage, FriendMessage],
        inline_dispatchers=[
            MatchRegex(r"^(?P<owner>[^/]+)/(?P<repo>[^/]+)#(?P<number>\d+)$")
        ],
    )
)
async def render_link(
    app: Ariadne,
    ev: GroupMessage | FriendMessage,
    owner_chain: Annotated[MessageChain, RegexGroup("owner")],
    repo_chain: Annotated[MessageChain, RegexGroup("repo")],
    issue_number: Annotated[MessageChain, RegexGroup("number")],
):
    owner, repo, number = owner_chain.display, repo_chain.display, issue_number.display
    gh = Launart.current().get_interface(GitHub)
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
            MatchRegex(r"^((https?://)?github\.com/)?(?P<owner>[^/]+)/(?P<repo>[^/]+)$")
        ],
    )
)
async def render_open_graph(
    app: Ariadne,
    ev: GroupMessage | FriendMessage,
    owner_chain: Annotated[MessageChain, RegexGroup("owner")],
    repo_chain: Annotated[MessageChain, RegexGroup("repo")],
):
    owner, repo = owner_chain.display, repo_chain.display
    client = Launart.current().get_interface(AiohttpClientInterface)
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


@channel.use(SchedulerSchema(every_minute()))
async def update_stat():
    # Poll GraiaProject + GraiaCommunity events
    ...
