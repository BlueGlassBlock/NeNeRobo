import msgspec
from githubkit import GitHub, TokenAuthStrategy
from kayaku import create

from library.send_util import EventCtx

SCOPES = ["gist", "project", "read:user", "repo", "write:discussion", "write:org"]


class DeviceCodeResp(msgspec.Struct):
    device_code: str
    user_code: str
    verification_uri: str
    expires_in: int
    interval: int


async def verify_auth(ctx: EventCtx, token: str) -> bool:
    from . import MasterCredential

    async with GitHub(TokenAuthStrategy(token)) as gh:
        for i in range(3):
            try:
                user_name = (
                    await gh.rest.users.async_get_authenticated()
                ).parsed_data.name
            except Exception:
                await ctx.send(f"Token 验证失败，重试：{i} / 3")
            else:
                await ctx.send(f"你已经为 {user_name} 安装过了！")
                await ctx.send(
                    f"请在 https://github.com/settings/connections/applications/{create(MasterCredential).client_id} 管理！",
                )
                return True
    return False
