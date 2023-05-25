import contextlib
import secrets
from dataclasses import field
from datetime import datetime
from pathlib import Path
from typing import Annotated

import msgspec
from graia.amnesia.builtins.aiohttp import AiohttpClientInterface
from ichika.client import Client
from ichika.graia.event import FriendMessage, GroupMessage
from ichika.message.elements import MessageChain, Image, Text
from graiax.shortcut.text_parser import MatchContent, MatchRegex, RegexGroup
from graiax.shortcut.interrupt import AnnotationWaiter
from library.validator import CertainFriend, Quoting
from graia.saya import Channel
from graia.saya.builtins.broadcast import ListenerSchema
from graia.scheduler.saya import SchedulerSchema
from graia.scheduler.timers import every_custom_seconds
from graiax.shortcut import FunctionWaiter, decorate, listen
from httpx import AsyncClient
from kayaku import config, create
from loguru import logger
from msgspec.msgpack import decode, encode

from library.storage import dir
from library.send_util import EventCtx, forward_node, msg

from .auth import SCOPES, DeviceCodeResp, verify_auth
from .render import files_changed_image, format_event, link_to_image
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
    app: Client,
    ev: GroupMessage | FriendMessage,
    owner_chain: Annotated[MessageChain, RegexGroup("owner")],
    repo_chain: Annotated[MessageChain, RegexGroup("repo")],
    issue_number: Annotated[MessageChain, RegexGroup("number")],
    gh: GitHub,
):
    owner, repo, number = map(str, (owner_chain, repo_chain, issue_number))
    ctx = EventCtx(app, ev)

    try:
        issue_prop_pull_request = (
            await gh.rest.issues.async_get(owner, repo, int(number))
        ).parsed_data.pull_request
    except Exception as e:
        return await ctx.send([ctx.as_reply, f"验证 Issue 失败：{repr(e)}"])

    try:
        receipt = await ctx.send(
            [
                ctx.as_reply,
                Image.build(
                    await link_to_image(
                        f"https://github.com/{owner}/{repo}/issues/{number}"
                    )
                ),
            ]
        )
    except TimeoutError:
        return await ctx.send([ctx.as_reply, "Timeout in 80000ms!"])

    if not issue_prop_pull_request:
        return

    waiter = AnnotationWaiter(MessageChain, [type(ev)], decorator=Quoting(receipt))

    while True:
        cmd = await waiter.wait(60)

        if cmd is None:
            return
        elif str(cmd.include(Text)).strip() == "diff":
            break

    try:
        card = await ctx.upload_forward(
            [
                forward_node(
                    ev.sender,
                    datetime.now(),
                    msg(Image.build(image)),
                )
                for image in await files_changed_image(
                    f"https://github.com/{owner}/{repo}/pull/{number}/files"
                )
            ]
        )
        await ctx.send(card)
    except TimeoutError:
        return await ctx.send([ctx.as_reply, "Timeout in 80000ms!"])


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
    app: Client,
    ev: GroupMessage | FriendMessage,
    owner_chain: Annotated[MessageChain, RegexGroup("owner")],
    repo_chain: Annotated[MessageChain, RegexGroup("repo")],
    client: AiohttpClientInterface,
    gh: GitHub,
):
    owner, repo = map(str, (owner_chain, repo_chain))
    ctx = EventCtx(app, ev)
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
        return await ctx.send(Image.build(pic))
    except Exception as e:
        return await ctx.send([ctx.as_reply, f"拉取 OpenGraph 失败：{repr(e)}"])


@channel.use(SchedulerSchema(every_custom_seconds(5)))
async def update_stat(app: Client, gh: GitHub):
    groups: list[int] = create(OrgMonitor).groups
    for events in gh.polls.values():
        while events and (ev := events.popleft()):
            # TODO: Render events
            logger.debug(repr(ev))
            if formatted := format_event(ev):
                for g in groups:
                    await app.send_group_message(g, msg(formatted))


DB = dir("github") / "objects.db"
DB.touch(exist_ok=True)


@listen(FriendMessage)
@decorate(MatchContent(".auth"))
async def gh_auth(app: Client, ev: FriendMessage):
    from . import MasterCredential

    ctx = EventCtx(app, ev)

    user_id: str = str(ev.sender.uin)
    DB.touch(exist_ok=True)
    data = DB.read_bytes() or encode({})
    db: dict[str, str] = decode(data, type=dict[str, str])
    if user_id in db:
        # validates token

        token = db[user_id]
        if await verify_auth(ctx, token):
            return
        del db[user_id]
        DB.write_bytes(encode(db))
        await ctx.send("授权似乎失效了，正在重新授权...")

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
        await ctx.send(
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
                if await verify_auth(ctx, token):
                    return token
            await ctx.send("授权失败，请重新授权！")
            return ""

        token = await FunctionWaiter(
            continue_cb,
            [FriendMessage],
            decorators=[MatchContent(".auth"), CertainFriend(ev.sender)],
            block_propagation=True,
        ).wait(timeout=90, default=None)
        if not token:
            return await ctx.send("授权超时，请重新授权！")
        db: dict[str, str] = decode(DB.read_bytes() or encode({}), type=dict[str, str])
        db[user_id] = token
        DB.write_bytes(encode(db))
