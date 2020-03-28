from typing import (
  List, Callable
)
import inspect
from mirai import Depend

class Command:
  match_string: str # 主匹配
  aliases: List[str] = [] # 一堆匹配, 但都类似于主匹配

  actions: List[Callable] = [] # 类似js的promise链
  priority: int = 0 # 优先级, 越大越会捕捉.
  dependencies: List[Depend] = []
  middlewares: List = []

  ways : List[str]

  def __init__(self,
    match_string: str,
    aliases: List[str] = [],
    priority: int = 0,
    dependencies: List[Depend] = [],
    middlewares: List = [],
    ways: List[str] = None
  ):
    self.priority = priority
    self.match_string = match_string
    self.aliases = aliases
    self.dependencies = dependencies
    self.middlewares = middlewares
    self.ways = ways or [
      "FriendMessage",
      "GroupMessage"
    ]
  
  def step(self, *args, **kwargs):
    def step_register(func):
      if not callable(func):
        raise TypeError("an action must be callable.")
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
      async def run(*args, **kwargs):
        result = await self.runner(self.getFristAction(), *args, **kwargs)
        for i in self.actions[1:]:
          result = await self.runner(i, result)
        return result
      frist_action = self.getFristAction()
      run.__name__ = frist_action.__name__
      run.__annotations__ = frist_action.__annotations__
      return run