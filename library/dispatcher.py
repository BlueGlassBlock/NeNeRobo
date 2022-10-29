import re
from typing import Optional

from graia.ariadne.event.message import MessageEvent
from graia.ariadne.message.chain import MessageChain
from graia.ariadne.message.parser.base import ChainDecorator
from graia.broadcast.entities.dispatcher import BaseDispatcher
from graia.broadcast.exceptions import ExecutionStop
from graia.broadcast.interfaces.dispatcher import DispatcherInterface
from launart import ExportInterface, Launart


class LaunartDispatcher(BaseDispatcher):
    async def catch(self, interface: DispatcherInterface):
        if isinstance(interface.annotation, type):
            if interface is Launart:
                return Launart.current()
            elif issubclass(interface.annotation, ExportInterface):
                return Launart.current().get_interface(interface.annotation)


class SearchRegex(ChainDecorator, BaseDispatcher):
    """匹配正则表达式"""

    def __init__(self, regex: str, flags: re.RegexFlag = re.RegexFlag(0)) -> None:
        self.regex: str = regex
        self.flags: re.RegexFlag = flags
        self.pattern = re.compile(self.regex, self.flags)
        self.match_func = self.pattern.search

    async def __call__(self, chain: MessageChain, _) -> Optional[MessageChain]:
        if not self.match_func(str(chain)):
            raise ExecutionStop
        return chain

    async def beforeExecution(self, interface: DispatcherInterface[MessageEvent]):
        _mapping_str, _map = interface.event.message_chain._to_mapping_str()
        if res := self.match_func(_mapping_str):
            interface.local_storage["__parser_regex_match_obj__"] = res
            interface.local_storage["__parser_regex_match_map__"] = _map
        else:
            raise ExecutionStop

    async def catch(self, interface: DispatcherInterface[MessageEvent]):
        if interface.annotation is re.Match:
            return interface.local_storage["__parser_regex_match_obj__"]
