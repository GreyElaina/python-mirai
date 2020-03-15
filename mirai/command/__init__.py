from mirai.application import Mirai
from mirai.event.message.chain import MessageChain
from mirai import (
    Member, Friend,
    Group, Any
)
from typing import (
    List, Dict, Callable
)
from .entity import Command
import parse

class CommandManager:
    main_application: Mirai
    command_prefix: str = "/"
    matches_commands: List[Command] = {}

    def __init__(self,
        app: Mirai,

        group_message: bool = True,
        friend_message: bool = True,

        command_prefix: str = "/"
    ):
        self.main_application = app
        self.command_prefix = command_prefix
        if group_message:
            app.receiver("GroupMessage")(self.group_message_handler)
        if friend_message:
            app.receiver("FriendMessage")(self.friend_message_handler)

    def sortCommands(self):
        self.matches_commands.sort(key=lambda x: x.priority, reverse=True)

    async def group_message_handler(self,
        app: Mirai, message: MessageChain,
        sender: Member, group: Group
    ):
        message_string = message.toString()
        for command in self.matches_commands:
            pass

    async def friend_message_handler(self):
        pass