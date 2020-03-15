from typing import (
    List, Callable
)
import inspect

class Command:
    match_string: str # 主匹配
    aliases: List[str] = [] # 一堆匹配
    actions: List[Callable] = [] # 类似js的promise链
    priority: int = 0 # 优先级, 越大越会捕捉.

    def __init__(self,
        match_string: str,
        aliases: List[str] = []
    ):
        self.match_string = match_string
        self.aliases = aliases
    
    def action(self, func):
        if not callable(func):
            raise TypeError("an action must be callable.")
        self.actions.append(func)
        return func

    @staticmethod
    async def runner(func, *args, **kwargs):
        if inspect.iscoroutinefunction(func):
            return await func(*args, **kwargs)
        else:
            return func(*args, **kwargs)

    def getFristAction(self):
        if self.actions:
            return self.actions[0]

    async def run(self, *args, **kwargs):
        if self.actions:
            result = self.runner(self.actions[0], *args, **kwargs)
            for i in self.actions[1:]:
                result = self.runner(i, *args, **kwargs)
            return result