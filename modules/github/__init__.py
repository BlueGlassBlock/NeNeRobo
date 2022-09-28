from graia.saya import Channel
from kayaku import ConfigModel
from launart import Launart

from .service import GitHub

channel = Channel.current()


class Credential(ConfigModel, domain="github.credential"):
    token: str
    """GitHub Token"""
