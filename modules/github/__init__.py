from graia.ariadne.app import Ariadne
from graia.ariadne.event.message import MessageEvent
from graia.ariadne.message.commander.saya import CommandSchema
from graia.ariadne.message.element import Image
from graia.saya import Channel
from kayaku import ConfigModel
from launart import Launart

from .renderer import issue_to_image
from .service import GitHub

channel = Channel.current()


class Credential(ConfigModel, domain="github.credential"):
    token: str | None = None
    """GitHub Token"""


@channel.use(CommandSchema("gh {owner: str} {repo: str} {number: int}"))
async def issue_render(
    app: Ariadne, ev: MessageEvent, owner: str, repo: str, number: int
):
    gh = Launart.current().get_interface(GitHub)
    issue = (await gh.rest.issues.async_get(owner, repo, number)).parsed_data
    return await app.send_message(ev, Image(data_bytes=await issue_to_image(issue)))
    # return await app.send_message(ev, repr(e))
