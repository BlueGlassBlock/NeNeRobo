import pkgutil
from dataclasses import field
import creart
import kayaku
from graia.ariadne.connection.config import from_obj
from graia.ariadne.entry import Ariadne
from graia.ariadne.message.commander.saya import CommanderBehaviour
from graia.saya import Saya
from graia.broadcast import Broadcast
from graiax.playwright import PlaywrightService
from kayaku import config, create, save_all
from launart import Launart, LaunartBehaviour
from loguru import logger
from library.dispatcher import LaunartDispatcher

if __name__ == "__main__":
    kayaku.initialize(
        {
            "{**}": "./config/{**}",
            "{**}.credential": "./config/credential.jsonc::{**}",
        }
    )
    saya = creart.it(Saya)
    bcc = creart.it(Broadcast)
    bcc.prelude_dispatchers.append(LaunartDispatcher)
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

    @config("account.credential")
    class Credential:
        accounts: list = field(default_factory=list)
        """List of Accounts."""

    cfg = create(Credential)
    if not cfg.accounts:
        raise ValueError("No account configured.")
    from_obj(cfg.accounts)
    Ariadne.launch_blocking()
    save_all()
