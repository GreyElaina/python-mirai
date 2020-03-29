from typing import (
  List, Callable
)
import inspect
from mirai import Depend, Group, Friend, Member, GroupMessage, FriendMessage

class Command:
  match_string: str # 主匹配
  aliases: List[str] # 一堆匹配, 但都类似于主匹配

  actions: List[Callable] # 类似js的promise链
  priority: int # 优先级, 越大越会捕捉.
  dependencies: List[Depend]
  middlewares: List

  ways : List[str]

  def __init__(self,
    match_string: str,
    aliases: List[str] = None,
    priority: int = None,
    dependencies: List[Depend] = None,
    middlewares: List = None,
    ways: List[str] = None
  ):
    self.priority = priority or 0
    self.match_string = match_string
    self.aliases = aliases or []
    self.dependencies = dependencies or []
    self.middlewares = middlewares or []
    self.actions = []
    self.ways = ways or [
      "FriendMessage",
      "GroupMessage"
    ]
  
  def step(self, *args, **kwargs):
    def step_register(func):
      if not callable(func):
        raise TypeError("an action must be callable.")
      for k, v in func.__annotations__.items():
        if v in [
          Group, Member, GroupMessage
        ]:
          if "FriendMessage" in self.ways:
            raise TypeError(f"you should set the ways currently: FriendMessage cannot use the annotations: {func}.{k}")
        elif v in [
          Friend, FriendMessage
        ]:
          if "FriendMessage" in self.ways:
            raise TypeError(f"you should set the ways currently: GroupMessage cannot use the annotations: {func}.{k}")
      self.actions.append(func)
      return func
    return step_register

  @staticmethod
  async def runner(func, *args, **kwargs):
    if inspect.iscoroutinefunction(func):
      return await func(*args, **kwargs)
    else:
      return func(*args, **kwargs)

  def getFristAction(self):
    if self.actions:
      return self.actions[0]

  def getInstance(self):
    if self.actions:
      frist_action = self.getFristAction()
      return frist_action