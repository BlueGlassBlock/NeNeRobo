import pkgutil
from typing import List

import creart
import kayaku
from graia.ariadne.connection.config import ConfigTypedDict, from_obj
from graia.ariadne.entry import Ariadne
from graia.ariadne.message.commander.saya import CommanderBehaviour
from graia.ariadne.util import RichLogInstallOptions
from graia.saya import Saya
from graiax.playwright import PlaywrightService
from kayaku import ConfigModel, create
from launart import Launart, LaunartBehaviour
from loguru import logger


class Credential(ConfigModel, domain="account.credential"):
    accounts: List[ConfigTypedDict] = []
    """List of Accounts."""


if __name__ == "__main__":
    logger.add("./logs/{time: YYYY-MM-DD}.log", rotation="00:00", encoding="utf-8")
    saya = creart.it(Saya)
    manager = Launart()
    manager.add_launchable(PlaywrightService())
    saya.install_behaviours(LaunartBehaviour(manager), creart.it(CommanderBehaviour))
    Ariadne.config(
        launch_manager=manager,
        install_log=RichLogInstallOptions(rich_traceback=True),
        inject_bypass_listener=True,
    )
    with saya.module_context():
        for module_info in pkgutil.iter_modules(["modules"]):
            saya.require(f"modules.{module_info.name}")
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
