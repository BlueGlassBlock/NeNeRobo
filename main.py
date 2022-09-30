import pkgutil
from typing import List

import creart
import kayaku
from graia.ariadne.connection.config import ConfigTypedDict, from_obj
from graia.ariadne.entry import Ariadne
from graia.ariadne.message.commander.saya import CommanderBehaviour
from graia.saya import Channel, Saya
from graiax.playwright import PlaywrightService
from kayaku import ConfigModel, create
from launart import Launart, LaunartBehaviour
from loguru import logger

from library.injector import inject


class Credential(ConfigModel, domain="account.credential"):
    accounts: List[ConfigTypedDict] = []
    """List of Accounts."""


if __name__ == "__main__":
    saya = creart.it(Saya)
    manager = Launart()
    manager.add_launchable(PlaywrightService())
    saya.install_behaviours(LaunartBehaviour(manager), creart.it(CommanderBehaviour))
    Ariadne.config(
        launch_manager=manager,
        inject_bypass_listener=True,
    )
    logger.add("./logs/{time: YYYY-MM-DD}.log", rotation="00:00", encoding="utf-8")
    with saya.module_context():
        for module_info in pkgutil.iter_modules(["modules"]):
            channel = saya.require(f"modules.{module_info.name}")
            if isinstance(channel, Channel):
                inject(channel)
    kayaku.initialize(
        {
            "{**}": "./config/{**}:",
            "{**}.credential": "./config/credential.jsonc:{**}",
        }
    )

    cfg = create(Credential)
    if not cfg.accounts:
        raise ValueError("No account configured.")
    from_obj(cfg.accounts)
    Ariadne.launch_blocking()
