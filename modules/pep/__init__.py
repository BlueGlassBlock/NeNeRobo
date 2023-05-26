import re
from typing import Annotated

from graiax.shortcut import dispatch, listen
from graiax.shortcut.text_parser import MatchRegex, RegexGroup
from ichika.client import Client
from ichika.graia.event import FriendMessage, GroupMessage, MessageEvent
from ichika.message.elements import Image, MessageChain

from library.send_util import EventCtx

from .render import PEP_to_image


@listen(GroupMessage, FriendMessage)
@dispatch(MatchRegex(r"PEP[ -]?(?P<index>\d+)", flags=re.IGNORECASE))
async def render_pep(
    app: Client,
    event: MessageEvent,
    index: Annotated[MessageChain, RegexGroup("index")],
):
    ctx = EventCtx(app, event)
    pep: int = int(str(index))
    try:
        image_bytes = await PEP_to_image(pep)
    except Exception as e:
        return await ctx.send(f"渲染 PEP {pep} 时发生错误：{e!r}")
    await ctx.send(Image.build(image_bytes))
