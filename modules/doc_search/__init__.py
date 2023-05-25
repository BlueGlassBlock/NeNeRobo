from datetime import datetime
from graia.saya import Channel
from ichika.core import Member, Friend
from ichika.client import Client
from ichika.message.elements import MessageChain, Image
from graiax.shortcut.commander import Arg
from graiax.shortcut.commander.saya import CommandSchema
from ichika.graia.event import MessageEvent
from library.send_util import EventCtx, msg, forward_node
from kayaku import create
from .render import results_to_images

channel: Channel = Channel.current()
from .service import SearchInterface, SphinxSearchConfig


def parse_query(phrase: str) -> str:
    return f'''"{'" AND "'.join(phrase.split(" "))}"'''


@channel.use(
    CommandSchema(
        create(SphinxSearchConfig).command,
        {
            "total": Arg("[--total|-t] {total}", int, 5),
            "max_height": Arg("[--max-height|-h] {max_height}", int, 5000),
        },
    )
)
async def handle(
    phrase: MessageChain,
    total: int,
    max_height: int,
    event: MessageEvent,
    app: Client,
    interface: SearchInterface,
    sender: Member | Friend,
):
    ctx = EventCtx(app, event)
    if total > 20:
        return await ctx.send(f"{total} 条太多了，最多 20 条！")
    elif total < 1:
        return await ctx.send(f"{total} 条这怎么搜")
    if max_height not in range(500, 17500):
        return await ctx.send(f"{max_height} 这个高度怎么想都不对劲吧")
    result = await interface.search(parse_query(str(phrase)), total)
    images = await results_to_images(result, max_height)
    forward_card = await ctx.upload_forward(
        [
            forward_node(
                sender,
                datetime.now(),
                msg(f"共有 {len(result)} 条结果"),
            ),
            *(
                forward_node(
                    sender,
                    datetime.now(),
                    msg(
                        [
                            f"#{idx}: {res.name} ({res.role})\n{res.uri}\n",
                            Image.build(data)
                            if isinstance(data := images.pop(res.uri, -1), bytes)
                            else f"元素高度为 {data}，无法截图",
                        ]
                    ),
                )
                for idx, res in enumerate(result, 1)
            ),
        ]
    )
    await ctx.send(forward_card)
