from dataclasses import field

from graia.saya import Channel
from graiax.shortcut import listen
from kayaku import config, create
from ichika.graia.event import NewFriendRequest
from ichika.client import Client

channel = Channel.current()


@config("friend.policy")
class FriendPolicy:
    accept_all: bool = False
    """Whether to accept every friend request"""
    whitelist: list[int] = field(default_factory=list)
    """Whitelist that allows user to be accepted even if `accept_all` is false."""
    reason: str = "管理者已关闭了自动加好友，请联系"
    """Reason of rejection"""


@listen(NewFriendRequest)
async def handle_request(app: Client, event: NewFriendRequest):
    policy = create(FriendPolicy, flush=True)
    if policy.accept_all or event.uin in policy.whitelist:
        return await app.process_new_friend_request(event.seq, event.uin, True)
    return await app.process_new_friend_request(event.seq, event.uin, False)
