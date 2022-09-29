from typing import Annotated

from graia.ariadne.app import Ariadne
from graia.ariadne.event.message import MessageEvent
from graia.ariadne.message.element import Image
from graia.ariadne.message.exp import MessageChain
from graia.ariadne.message.parser.base import MatchRegex, RegexGroup
from graia.saya import Channel
from graia.saya.builtins.broadcast import ListenerSchema
from kayaku import ConfigModel
from launart import Launart

from .renderer import issue_to_image
from .service import GitHub

channel = Channel.current()


class Credential(ConfigModel, domain="github.credential"):
    token: str | None = None
    """GitHub Token"""


@channel.use(
    ListenerSchema(
        [MessageEvent],
        inline_dispatchers=[
            MatchRegex(
                r"((https?://)?github\.com/)?(?P<owner>[^/]+)/(?P<repo>[^/]+)/(issues|pull)/(?P<number>\d+)"
            )
        ],
    )
)
@channel.use(
    ListenerSchema(
        [MessageEvent],
        inline_dispatchers=[
            MatchRegex(r"(?P<owner>[^/]+)/(?P<repo>[^/]+)#(?P<number>\d+)")
        ],
    )
)
async def render(
    app: Ariadne,
    ev: MessageEvent,
    owner_chain: Annotated[MessageChain, RegexGroup("owner")],
    repo_chain: Annotated[MessageChain, RegexGroup("repo")],
    issue_number: Annotated[MessageChain, RegexGroup("number")],
):
    owner, repo = owner_chain.display, repo_chain.display
    number: int = int(issue_number.display)
    gh = Launart.current().get_interface(GitHub)
    try:
        issue = (await gh.rest.issues.async_get(owner, repo, number)).parsed_data
        return await app.send_message(
            ev, Image(data_bytes=await issue_to_image(issue)), quote=ev.source
        )
    except Exception as e:
        return await app.send_message(ev, repr(e), quote=ev.source)
