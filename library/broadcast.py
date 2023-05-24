from graia.broadcast import Broadcast
from graia.broadcast.entities.listener import Listener
from graia.broadcast.entities.dispatcher import BaseDispatcher
from graia.broadcast.interfaces.dispatcher import DispatcherInterface
from launart import ExportInterface, Launart


class LaunartDispatcher(BaseDispatcher):
    async def catch(self, interface: DispatcherInterface):
        if isinstance(interface.annotation, type):
            if interface is Launart:
                return Launart.current()
            elif issubclass(interface.annotation, ExportInterface):
                return Launart.current().get_interface(interface.annotation)


def inject_bypass_listener(broadcast: Broadcast):
    """注入 BypassListener 以享受子事件解析.

    Args:
        broadcast (Broadcast): 外部事件系统, 提供了 event_class_generator 方法以生成子事件.
    """

    class BypassListener(Listener):
        """透传监听器的实现"""

        def __init__(
            self,
            callable,
            namespace,
            listening_events,
            inline_dispatchers=None,
            decorators=None,
            priority: int = 16,
        ) -> None:
            events = []
            for event in listening_events:
                events.append(event)
                events.extend(broadcast.event_class_generator(event))
            super().__init__(
                callable,
                namespace,
                events,
                inline_dispatchers=inline_dispatchers or [],
                decorators=decorators or [],
                priority=priority,
            )

    import creart

    import graia.broadcast.entities.listener

    graia.broadcast.entities.listener.Listener = BypassListener  # type: ignore
    graia.broadcast.Listener = BypassListener  # type: ignore

    if creart.exists_module("graia.saya"):
        import graia.saya.builtins.broadcast.schema

        graia.saya.builtins.broadcast.schema.Listener = BypassListener  # type: ignore
