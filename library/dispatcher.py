from graia.broadcast.entities.dispatcher import BaseDispatcher
from graia.broadcast.interfaces.dispatcher import DispatcherInterface
from launart import Launart, ExportInterface


class LaunartDispatcher(BaseDispatcher):
    async def catch(self, interface: DispatcherInterface):
        if isinstance(interface.annotation, type):
            if interface is Launart:
                return Launart.current()
            elif issubclass(interface.annotation, ExportInterface):
                return Launart.current().get_interface(interface.annotation)
