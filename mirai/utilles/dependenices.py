from mirai.depend import Depend
from mirai import MessageChain, Cancelled, Image, Mirai, At
import re
from typing import List

def regex(pattern):
    async def regex_depend_wrapper(message: MessageChain):
        if not re.match(pattern, message.toString()):
            raise Cancelled
    return Depend(regex_depend_wrapper)

def startswith(string):
    async def startswith_wrapper(message: MessageChain):
        if not message.toString().startswith(string):
            raise Cancelled
    return Depend(startswith_wrapper)

def photo(num=1):
    "断言消息中图片的数量"
    async def photo_wrapper(message: MessageChain):
        if len(message.getAllofComponent(Image)) < num:
            raise Cancelled
    return Depend(photo_wrapper)

def at(qq=None):
    "判断是否at了某人, 如果没有则判断是否at了机器人"
    async def at_wrapper(app: Mirai, message: MessageChain):
        at_set: List[At] = message.getAllofComponent(At)
        qq = qq or app.qq
        if at_set:
            for at in at_set:
                if at.target == qq:
                    return
        else:
            raise Cancelled
    return Depend(at_wrapper)