import msgspec
from githubkit import GitHub, TokenAuthStrategy
from graia.ariadne.app import Ariadne
from graia.ariadne.event.message import FriendMessage
from kayaku import create

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
