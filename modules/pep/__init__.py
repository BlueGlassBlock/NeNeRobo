from library.dispatcher import SearchRegex
from .render import PEP_to_image
from graia.ariadne.app import Ariadne
from graia.ariadne.event.message import MessageEvent
from graiax.shortcut import listen, dispatch
from typing import Annotated

from graia.ariadne.app import Ariadne
from graia.ariadne.message.element import Image
from graia.ariadne.message.exp import MessageChain
from graia.ariadne.message.parser.base import RegexGroup
import re


@listen(MessageEvent)
@dispatch(SearchRegex(r"PEP[ -]?(?P<index>\d+)", flags=re.IGNORECASE))
async def render_pep(
    app: Ariadne, ev: MessageEvent, index: Annotated[MessageChain, RegexGroup("index")]
):
    pep: int = int(index.display)
    try:
        image_bytes = await PEP_to_image(pep)
    except Exception as e:
        return await app.send_message(ev, f"渲染 PEP {pep} 时发生错误：{e!r}")
    return await app.send_message(ev, [Image(data_bytes=image_bytes)])
