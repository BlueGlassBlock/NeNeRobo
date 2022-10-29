from typing import TYPE_CHECKING, cast

from graia.ariadne.util import Dummy
from graia.saya import Channel

try:
    channel: Channel = Channel.current()
    from .service import SearchInterface
except LookupError:
    if TYPE_CHECKING:
        channel: Channel = Channel.current()
        from .service import SearchInterface
    else:
        SearchInterface = channel = Dummy()
