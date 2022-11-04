import contextlib
import secrets
from dataclasses import field
from pathlib import Path
from typing import Annotated

import msgspec
from graia.amnesia.builtins.aiohttp import AiohttpClientInterface
from graia.ariadne.app import Ariadne
from graia.ariadne.event.message import FriendMessage, GroupMessage
from graia.ariadne.message.element import Image
from graia.ariadne.message.chain import MessageChain
from graia.ariadne.message.parser.base import MatchContent, MatchRegex, RegexGroup
from graia.ariadne.util.validator import CertainFriend
from graia.saya import Channel
from graia.saya.builtins.broadcast import ListenerSchema
from graia.scheduler.saya import SchedulerSchema
from graia.scheduler.timers import every_custom_seconds
from graiax.shortcut import FunctionWaiter, decorate, listen
from httpx import AsyncClient
from kayaku import config, create
from loguru import logger
from msgspec.msgpack import decode, encode

from .auth import SCOPES, DeviceCodeResp, verify_auth
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


WORD = r"[A-Za-z0-9_-]"


@channel.use(
    ListenerSchema(
        [GroupMessage, FriendMessage],
        inline_dispatchers=[
            MatchRegex(
                rf"((https?://)?github\.com/)?(?P<owner>{WORD}+)/(?P<repo>{WORD}+)/(issues|pull)/(?P<number>\d+)",
                full=True,
            )
        ],
    )
)
@channel.use(
    ListenerSchema(
        [GroupMessage, FriendMessage],
        inline_dispatchers=[
            MatchRegex(
                rf"(?P<owner>{WORD}+)/(?P<repo>{WORD}+)#(?P<number>\d+)",
                full=True,
            ),
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
                rf"((https?://)?github\.com/)?(?P<owner>{WORD}+)/(?P<repo>{WORD}+)",
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
    gh: GitHub,
):
    owner, repo = owner_chain.display, repo_chain.display
    try:
        await gh.rest.repos.async_get(owner, repo)
    except Exception as e:
        return
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
    if app.launch_manager.status.preparing:
        return
    gh = app.launch_manager.get_interface(GitHub)
    groups: list[int] = create(OrgMonitor).groups
    for events in gh.polls.values():
        while events and (ev := events.popleft()):
            # TODO: Render events
            logger.debug(repr(ev))
            if formatted := format_event(ev):
                for g in groups:
                    await app.send_group_message(g, formatted)


DB = Path(__file__, "..", "tokens.db").resolve()


@listen(FriendMessage)
@decorate(MatchContent(".auth"))
async def gh_auth(app: Ariadne, ev: FriendMessage):
    from . import MasterCredential

    user_id: str = str(ev.sender.id)
    DB.touch(exist_ok=True)
    data = DB.read_bytes() or encode({})
    db: dict[str, str] = decode(data, type=dict[str, str])
    if user_id in db:
        # validates token

        token = db[user_id]
        if await verify_auth(app, ev, token):
            return
        del db[user_id]
        DB.write_bytes(encode(db))
        await app.send_message(ev, "授权似乎失效了，正在重新授权...")

    async with AsyncClient(headers={"Accept": "application/json"}) as client:
        resp: DeviceCodeResp = msgspec.json.decode(
            (
                await client.post(
                    "https://github.com/login/device/code",
                    json={
                        "client_id": create(MasterCredential).client_id,
                        "scope": ",".join(SCOPES),
                    },
                )
            ).content,
            type=DeviceCodeResp,
        )
        await app.send_message(
            ev,
            f"请在 {resp.verification_uri}\n"
            f"输入 {resp.user_code} 进行授权！\n"
            "完成后请发送 `.auth` 继续",
        )

        async def continue_cb() -> str:
            with contextlib.suppress(Exception):
                token: str = (
                    await client.post(
                        "https://github.com/login/oauth/access_token",
                        json={
                            "client_id": create(MasterCredential).client_id,
                            "device_code": resp.device_code,
                            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                        },
                    )
                ).json()["access_token"]
                if await verify_auth(app, ev, token):
                    return token
            await app.send_message(ev, "授权失败，请重新授权！")
            return ""

        token = await FunctionWaiter(
            continue_cb,
            [FriendMessage],
            decorators=[MatchContent(".auth"), CertainFriend(ev.sender)],
            block_propagation=True,
        ).wait(timeout=90, default=None)
        if not token:
            return await app.send_message(ev, "授权超时，请重新授权！")
        db: dict[str, str] = decode(DB.read_bytes() or encode({}), type=dict[str, str])
        db[user_id] = token
        DB.write_bytes(encode(db))
