from mirai.application import Mirai
from mirai.event.message.chain import MessageChain
from mirai import (
  Member, Friend,
  Group, Plain, Depend,
  
  At, Face, Image, AtAll, Source, Quote,

  InternalEvent,

  GroupMessage, FriendMessage
)
from mirai.misc import raiser
from mirai.logger import Session as SessionLogger
from typing import (
  List, Dict, Callable, Any
)
from .entity import Command
import parse
import aiohttp
import re
import random
import asyncio

"<name> [<arg1_name>:<aliases in annotation, fk 'return'> [, <arg2_name>:<method>]]"
"hso <change_status> [string:__string__]"

class CommandManager:
  main_application: Mirai
  command_prefix: str = ">"
  matches_commands: List[Command] = []

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
    if self.command_prefix == "/": # 特殊规则.
      SessionLogger.warn("if you setted a manager for someone in mirai-console, he or she won't action ANY command in there.")
      app.subroutine(self.mirai_console_builtins_wrapper)

  def sortCommands(self):
    #self.matches_commands.sort(key=lambda x: x.priority, reverse=True)
    result = {}
    for command in self.matches_commands:
      result.setdefault(command.priority, [])
      result[command.priority].append(command)
    for command_set in result.values():
      command_set.sort(key=lambda x: x.match_string, reverse=True)
    self.matches_commands = list(reversed(sum([result[i] for i in sorted(result)], [])))

  def registerCommand(self, command_instance):
    self.matches_commands.append(command_instance)

  async def group_message_handler(self,
    app: Mirai, message: MessageChain,
    sender: Member, group: Group,
    gm: GroupMessage
  ):
    message_string = message.toString()
    if message_string.startswith(self.command_prefix):
      mapping = {"".join(random.choices("qwertyuiopasdfghjklzxcvbnm", k=12)): i for i in message}
      string = "".join([v.toString() if isinstance(v, (
        Plain,
        Source,
        Quote,
      )) else k for k, v in mapping.items()])
      for i in self.matches_commands:
        for j in [i.match_string, *i.aliases]:
          compile_result = self.compileSignature(j, string[1:], { # qtmd prefix
            "At": lambda x: mapping[x.strip()] \
              if x.strip() in mapping and \
                mapping[x.strip()].__class__ == At
              else raiser(
                TypeError("Should be a At component.")
              ),
            "Face": lambda x: mapping[x.strip()] \
              if x.strip() in mapping and \
                mapping[x.strip()].__class__ == Face else raiser(
                TypeError("Should be a Face component.")
              ),
            "Image": lambda x: mapping[x.strip()] \
              if x.strip() in mapping and \
                mapping[x.strip()].__class__ == Image else raiser(
                TypeError("Should be a Image component.")
              ),
            "AtAll": lambda x: mapping[x.strip()] \
              if x.strip() in mapping and \
                mapping[x.strip()].__class__ == AtAll else raiser(
                TypeError("Should be a AtAll component.")
              ),
          })
          if compile_result:
            # 检查
            if compile_result.fixed:
              SessionLogger.warn(f"catched a unnamed argument, it will be passed: {compile_result.fixed} on {gm}")
            
            checker_named_value = [
              (i.strip() in mapping) if isinstance(i, str) \
                else False \
                  for i in compile_result.named.values()]
            if True in checker_named_value:
              wrong_key = list(compile_result.named.keys())[
                checker_named_value.index(True)
              ]
              SessionLogger.error(f"a wrong argument catched, because of the special value: {wrong_key} in {i}, catched on {gm}")
              return
            # 可以开始传值了.

            loop: asyncio.AbstractEventLoop = asyncio.get_running_loop()
            loop.create_task(self.main_application.main_entrance(
              {
                "func": i.getInstance(),
                "middlewares": i.middlewares + self.main_application.global_middlewares,
                "dependencies": i.dependencies + self.main_application.global_dependencies
              }, InternalEvent(
                name="GroupMessage",
                body=gm
              ), compile_result.named
            ))
        else:
          break

  async def friend_message_handler(self,
    app: Mirai, message: MessageChain,
    sender: Friend, fm: FriendMessage
  ):
    message_string = message.toString()
    if message_string.startswith(self.command_prefix):
      mapping = {"".join(random.choices("qwertyuiopasdfghjklzxcvbnm", k=12)): i for i in message}
      string = "".join([v.toString() if isinstance(v, (
        Plain,
        Source,
      )) else k for k, v in mapping.items()])
      for i in self.matches_commands:
        for j in [i.match_string, *i.aliases]:
          compile_result = self.compileSignature(j, string[1:], { # qtmd prefix
            "Face": lambda x: mapping[x.strip()] \
              if x.strip() in mapping and \
                mapping[x.strip()].__class__ == Face else raiser(
                TypeError("Should be a Face component.")
              ),
            "Image": lambda x: mapping[x.strip()] \
              if x.strip() in mapping and \
                mapping[x.strip()].__class__ == Image else raiser(
                TypeError("Should be a Image component.")
              )
          })
          if compile_result:
            # 检查
            if compile_result.fixed:
              SessionLogger.warn(f"catched a unnamed argument, it will be passed: {compile_result.fixed} on {fm}")
            
            checker_named_value = [
              (i.strip() in mapping) if isinstance(i, str) \
                else False \
                  for i in compile_result.named.values()]
            if True in checker_named_value:
              wrong_key = list(compile_result.named.keys())[
                checker_named_value.index(True)
              ]
              SessionLogger.error(f"a wrong argument catched, because of the special value: {wrong_key} in {i}, catched on {fm}")
              return
            # 可以开始传值了.

            loop: asyncio.AbstractEventLoop = asyncio.get_running_loop()
            loop.create_task(self.main_application.main_entrance(
              {
                "func": i.getInstance(),
                "middlewares": i.middlewares + self.main_application.global_middlewares,
                "dependencies": i.dependencies + self.main_application.global_dependencies
              }, InternalEvent(
                name="FriendMessage",
                body=fm
              ), compile_result.named
            ))
            break
        else:
          break

  async def mirai_console_builtins_wrapper(self):
    """不应该在 prefix != / 时启动.  
    专门用于处理当 Sender 被指定为 Manager 时无法使用常规的 FriendMessage/GroupMessage
    进行指令监听的情况.  
    由于目前, httpapi command 接口并非完全完善, 故暂时不兼容.
    """
    async with aiohttp.ClientSession() as session:
      async with session.ws_connect(
        f"{self.main_application.baseurl}/command?authKey={self.main_application.auth_key}"
      ) as ws_connection:
        while True:
          try:
            received_data = await ws_connection.receive_json()
          except TypeError:
            continue
          if received_data:
            message_string = " ".join([received_data['name'], *received_data['args']])

  def newAction(self, 
    match_string: str,
    aliases: List[str] = [],
    priority: int = 0,
    dependencies: List[Depend] = [],
    middlewares: List = []
  ):
    new_command = Command(
      match_string,
      aliases, priority,
      dependencies, middlewares
    )
    self.registerCommand(new_command)
    self.sortCommands()
    return new_command

  def newMark(self, 
    match_string: str,
    aliases: List[str] = None,
    priority: int = None,
    dependencies: List[Depend] = None,
    middlewares: List = None
  ):
    def register(func):
      new_command = Command(
        match_string,
        aliases or [], priority or 0,
        dependencies or [], middlewares or []
      )
      self.registerCommand(new_command)
      self.sortCommands()
      new_command.step()(func)
      return func
    return register

  @staticmethod
  def compileSignature(signature_string: str, target_string: str, mapping: dict):
    return parse.parse(signature_string, target_string, mapping)