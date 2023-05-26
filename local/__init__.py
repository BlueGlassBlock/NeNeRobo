import pkgutil
from dataclasses import field

import kayaku
from graia.broadcast.builtin.decorators import Depend
from graia.broadcast.exceptions import ExecutionStop
from graia.saya import Channel, Saya
from graia.broadcast import Broadcast
from ichika.client import Client
from ichika.graia.event import GroupMessage

from library.send_util import EventCtx
from library.validator import CertainGroup

saya = Saya.current()


@kayaku.config("local")
class LocalConfig:
    target_groups: list[int] = field(default_factory=list)
    admins: list[int] = field(default_factory=list)
    permission_error: str = "没有权限执行此操作"


@Depend
async def require_admin(client: Client, event: GroupMessage):
    cfg = kayaku.create(LocalConfig)
    if event.group.uin not in cfg.target_groups:
        raise ExecutionStop
    if event.sender.uin not in cfg.admins:
        ctx = EventCtx(client, event)
        await ctx.send(cfg.permission_error)
        raise ExecutionStop


channel = Channel.current()


for mod_info in pkgutil.iter_modules(["local"]):
    saya.require(f"local.{mod_info.name}")

import creart

bcc = creart.it(Broadcast)

for listener in bcc.listeners:
    if listener.callable.__module__.startswith("local"):
        listener.decorators.append(
            CertainGroup(kayaku.create(LocalConfig).target_groups)
        )
