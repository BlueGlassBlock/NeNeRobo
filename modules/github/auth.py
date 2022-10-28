import contextlib
from pathlib import Path

import msgspec
from githubkit import GitHub, TokenAuthStrategy
from graia.ariadne.app import Ariadne
from graia.ariadne.event.message import FriendMessage
from graia.ariadne.message.parser.base import MatchContent
from graia.ariadne.util.validator import CertainFriend
from graiax.shortcut import FunctionWaiter, decorate, listen
from httpx import AsyncClient
from kayaku import create
from msgspec.msgpack import decode, encode

DB = Path(__file__) / "tokens.db"

SCOPES = ["gist", "project", "read:user", "repo", "write:discussion", "write:org"]


class DeviceCodeResp(msgspec.Struct):
    device_code: str
    user_code: str
    verification_uri: str
    expires_in: int
    interval: int


async def verify_auth(app: Ariadne, ev: FriendMessage, token: str) -> bool:
    from . import MasterCredential

    async with GitHub(TokenAuthStrategy(token)) as gh:
        for i in range(3):
            try:
                user_name = (
                    await gh.rest.users.async_get_authenticated()
                ).parsed_data.name
            except Exception:
                await app.send_message(ev, f"Token 验证失败，重试：{i} / 3")
            else:
                await app.send_message(ev, f"你已经为 {user_name} 安装过了！")
                await app.send_message(
                    ev,
                    f"请在 https://github.com/settings/connections/applications/{create(MasterCredential).client_id} 管理！",
                )
                return True
    return False


@listen(FriendMessage)
@decorate(MatchContent(".auth"))
async def gh_auth(app: Ariadne, ev: FriendMessage):
    from . import MasterCredential

    user_id: str = str(ev.sender.id)
    db: dict[str, str] = decode(DB.read_bytes(), type=dict[str, str])
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
                if verify_auth(app, ev, token):
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
        db: dict[str, str] = decode(DB.read_bytes(), type=dict[str, str])
        db[user_id] = token
        DB.write_bytes(encode(db))
