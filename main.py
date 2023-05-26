from asyncio import AbstractEventLoop
import atexit
import pkgutil
from typing import Optional

import creart
import kayaku
from graia.amnesia.builtins.aiohttp import AiohttpClientService
from ichika.graia import IchikaComponent
from ichika.login import PasswordProtocol, PathCredentialStore
from graiax.shortcut.commander import Commander
from graiax.shortcut.commander.saya import CommanderBehaviour
from graia.broadcast import Broadcast
from graia.saya import Saya
from graiax.playwright import PlaywrightService
from launart import Launart, LaunartBehaviour
from loguru import logger

from library.broadcast import LaunartDispatcher, inject_bypass_listener


def create_commander(broadcast: Broadcast) -> Commander:
    from ichika.graia import BROADCAST_EVENT
    from ichika.graia.event import GroupMessage, FriendMessage
    from graia.broadcast.entities.listener import Listener

    cmd = Commander(broadcast, BROADCAST_EVENT)
    broadcast.listeners.append(
        Listener(
            cmd.execute,
            broadcast.getDefaultNamespace(),
            [GroupMessage, FriendMessage],
            priority=15,
        )
    )
    return cmd


if __name__ == "__main__":
    kayaku.initialize(
        {
            "{**}": "./config/{**}",
            "{**}.credential": "./config/credential.jsonc::{**}",
            "local.{**}": "./config/local.jsonc::{**}",
        }
    )
    atexit.register(kayaku.save_all)
    saya = creart.it(Saya)
    bcc = creart.it(Broadcast)
    inject_bypass_listener(bcc)
    bcc.prelude_dispatchers.append(LaunartDispatcher())
    manager = Launart()
    manager.add_launchable(PlaywrightService())
    manager.add_launchable(AiohttpClientService())
    saya.install_behaviours(
        LaunartBehaviour(manager),
        CommanderBehaviour(create_commander(bcc)),
    )

    logger.add("./logs/{time: YYYY-MM-DD}.log", rotation="00:00", encoding="utf-8")
    with saya.module_context():
        for module_info in pkgutil.iter_modules(["modules"]):
            channel = saya.require(f"modules.{module_info.name}")
        saya.require("local")

    @kayaku.config("account.credential")
    class IchikaCredential:
        account: int
        """Account"""
        password: Optional[str] = None
        """Password, use QRCode login when unset"""
        protocol: PasswordProtocol = "AndroidPad"
        """Protocol, could be AndroidPhone, AndroidPad, IPad"""

    kayaku.bootstrap()

    cfg = kayaku.create(IchikaCredential)
    comp = IchikaComponent(PathCredentialStore("./data/bots"), bcc)

    if cfg.password is None:
        comp.add_qrcode_login(cfg.account)
    else:
        comp.add_password_login(cfg.account, cfg.password, cfg.protocol)

    manager.add_launchable(comp)
    manager.launch_blocking(loop=creart.it(AbstractEventLoop))
