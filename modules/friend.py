from dataclasses import field

from graia.saya import Channel
from graiax.shortcut import listen
from kayaku import config, create
from graia.ariadne.event.mirai import NewFriendRequestEvent

channel = Channel.current()


@config("friend.policy")
class FriendPolicy:
    accept_all: bool = False
    """Whether to accept every friend request"""
    whitelist: list[int] = field(default_factory=list)
    """Whitelist that allows user to be accepted even if `accept_all` is false."""
    reason: str = "管理者已关闭了自动加好友，请联系"
    """Reason of rejection"""


@listen(NewFriendRequestEvent)
async def handle_request(event: NewFriendRequestEvent):
    policy = create(FriendPolicy, flush=True)
    if policy.accept_all or event.supplicant in policy.whitelist:
        return await event.accept()
    return await event.reject(policy.reason)
