from contextlib import suppress
from typing import Generic, Optional, Sequence, Set, Type, Union, TypeVar

from graia.broadcast.entities.decorator import Decorator
from graia.broadcast.exceptions import ExecutionStop, RequirementCrashed
from graia.broadcast.interfaces.decorator import DecoratorInterface

from ichika.message.elements import Reply, MessageChain
from ichika.core import (
    Friend,
    Group,
    Member,
    MessageSource as Source,
    RawMessageReceipt,
)

T = TypeVar("T")


class Certain(Decorator, Generic[T]):
    pre = True

    def __init__(self, value: T, annotation: Optional[Type[T]] = None) -> None:
        self.value: T = value
        self.annotation: Type[T] = annotation or value.__class__

    async def target(self, i: DecoratorInterface):
        try:
            val: T = await i.dispatcher_interface.lookup_param(
                "__decorator_parameter__", self.annotation, None
            )
        except RequirementCrashed as e:
            raise ExecutionStop from e
        if not self.comp(val):
            raise ExecutionStop
        return val

    def comp(self, value: T) -> bool:
        return value == self.value


SequenceOrInstance = Union[Sequence[T], T]


class CertainGroup(Certain):
    """需要消息发送/事件触发在指定群组"""

    value: Set[int]

    def __init__(self, group: SequenceOrInstance[Union[Group, int]]):
        """
        Args:
            group (SequenceOrInstance[Union[Group, int]]): 一个群/群号的列表/对象
        """
        group = list(group) if isinstance(group, Sequence) else [group]
        super().__init__({g if isinstance(g, int) else g.uin for g in group}, Group)

    def comp(self, value: Group) -> bool:
        return value.uin in self.value


class CertainFriend(Certain):
    """需要消息发送者/事件触发者是指定好友"""

    value: Set[int]

    def __init__(self, friend: SequenceOrInstance[Union[Friend, int]]):
        """
        Args:
            friend (SequenceOrInstance[Union[Friend, int]]): 一个好友/好友 QQ 号的列表/对象
        """
        friend = list(friend) if isinstance(friend, Sequence) else [friend]
        super().__init__({f if isinstance(f, int) else f.uin for f in friend}, Friend)

    def comp(self, value: Friend) -> bool:
        return value.uin in self.value


class CertainMember(Certain):
    """需要发送者/事件触发者是指定群员"""

    value: Set[int]
    group: Optional[Set[int]]

    def __init__(
        self,
        member: SequenceOrInstance[Union[Member, int]],
        group: Optional[SequenceOrInstance[Union[Member, int]]] = None,
    ):
        """
        Args:
            member (SequenceOrInstance[Union[Member, int]]): 成员或成员QQ号的列表/对象
            group (SequenceOrInstance[Union[Group, int]], optional): 如果提供, 则要求群员在传入的群内
        """
        member = list(member) if isinstance(member, Sequence) else [member]
        super().__init__({m if isinstance(m, int) else m.uin for m in member}, Member)
        self.group = None
        if group:
            group = list(group) if isinstance(group, Sequence) else [group]
            self.group = {g if isinstance(g, int) else g.uin for g in group}

    def comp(self, value: Member) -> bool:
        return value.uin in self.value and (
            not self.group or value.group_uin in self.group
        )


class Quoting(Decorator):
    """需要回复指定的消息"""

    pre = True

    msg_ids: Set[int]

    def __init__(self, message: SequenceOrInstance[Union[RawMessageReceipt, Source]]):
        """
        Args:
            message (SequenceOrInstance[Union[int, ActiveMessage, Source]]): 要回复的指定信息
        """
        if not isinstance(message, Sequence):
            message = [message]
        self.msg_ids = set()
        for msg in message:
            self.msg_ids.add(msg.seq)

    async def target(self, i: DecoratorInterface):
        with suppress(RequirementCrashed):
            chain: MessageChain = await i.dispatcher_interface.lookup_param(
                "__decorator_parameter_quote__", MessageChain, None
            )
            if (replies := chain.get(Reply)) and any(
                r.seq in self.msg_ids for r in replies
            ):
                return await i.dispatcher_interface.lookup_param(
                    "__decorator_parameter__", MessageChain, None
                )
        raise ExecutionStop
