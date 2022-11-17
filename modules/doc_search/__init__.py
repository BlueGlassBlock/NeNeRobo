from datetime import datetime
from graia.saya import Channel
from graia.ariadne.model import Friend, Member
from graia.ariadne.message.element import Forward, ForwardNode, Image
from graia.ariadne.event.message import MessageEvent
from graia.ariadne.message.commander.saya import CommandSchema
from graia.ariadne.message.chain import MessageChain
from graia.ariadne.message.commander import Arg
from graia.ariadne import Ariadne
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
    app: Ariadne,
    interface: SearchInterface,
    sender: Member | Friend,
):
    if total > 20:
        return await app.send_message(event, f"{total} 条太多了，最多 20 条！")
    elif total < 1:
        return await app.send_message(event, f"{total} 条这怎么搜")
    if max_height not in range(500, 17500):
        return await app.send_message(event, f"{max_height} 这个高度怎么想都不对劲吧")
    result = await interface.search(parse_query(str(phrase)), total)
    images = await results_to_images(result, max_height)
    return await app.send_message(
        event,
        [
            Forward(
                ForwardNode(
                    sender,
                    datetime.now(),
                    MessageChain(f"共有 {len(result)} 条结果"),
                ),
                (
                    ForwardNode(
                        sender,
                        datetime.now(),
                        MessageChain(
                            f"#{idx}: {res.name} ({res.role})\n{res.uri}\n",
                            Image(data_bytes=data)
                            if isinstance(data := images.pop(res.uri, -1), bytes)
                            else f"元素高度为 {data}，无法截图",
                        ),
                    )
                    for idx, res in enumerate(result, 1)
                ),
            )
        ],
    )
