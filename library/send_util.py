from ichika.graia.event import MessageEvent, GroupMessage, FriendMessage
from ichika.client import Client
from ichika.core import RawMessageReceipt as MessageReceipt, Friend, Member
from datetime import datetime
from functools import partial
from ichika.message.elements import (
    MessageChain,
    Element,
    Text,
    ForwardCard,
    ForwardMessage,
    Reply,
)
from typing import Callable, Awaitable


def msg(msg: str | Element | list[str | Element] | MessageChain) -> MessageChain:
    if isinstance(msg, (str, Element)):
        msg = [msg]
    if isinstance(msg, list):
        msg = MessageChain([Text(e) if isinstance(e, str) else e for e in msg])
    return msg


def forward_node(
    user: Member | Friend, time: datetime, chain: MessageChain
) -> ForwardMessage:
    if isinstance(user, Member):
        return ForwardMessage(user.uin, time, user.card_name, chain)
    else:
        return ForwardMessage(user.uin, time, user.nick, chain)


class EventCtx:
    client: Client
    event: MessageEvent
    __sender_fn: Callable[[MessageChain], Awaitable[MessageReceipt]]

    def __init__(self, client: Client, event: MessageEvent):
        self.client = client
        self.event = event

        if isinstance(self.event, GroupMessage):
            self.__sender_fn = partial(
                self.client.send_group_message, self.event.group.uin
            )
        elif isinstance(self.event, FriendMessage):
            self.__sender_fn = partial(
                self.client.send_friend_message, self.event.sender.uin
            )

    @property
    def as_reply(self) -> Reply:
        ev = self.event
        return Reply(
            ev.source.seq,
            ev.sender.uin,
            ev.source.time,
            str(ev.content),
        )

    async def send(
        self, message: str | Element | list[str | Element] | MessageChain
    ) -> MessageReceipt:
        return await self.__sender_fn(msg(message))

    async def upload_forward(self, msgs: list[ForwardMessage]) -> ForwardCard:
        if isinstance(self.event, GroupMessage):
            g_uin = self.event.group.uin
        else:
            g_uin = (await self.client.get_groups())[0].uin
        return await self.client.upload_forward_msg(g_uin, msgs)
