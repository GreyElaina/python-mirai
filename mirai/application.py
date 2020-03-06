from urllib import parse
from typing import Union, List, Dict, Optional, Callable, Any, Awaitable, NamedTuple
import typing as T
import asyncio
from functools import partial
import copy
import inspect

from mirai.misc import raiser

from mirai.event.builtins import UnexpectedException
from mirai.depend import Depend
from mirai.event import ExternalEvent, ExternalEventTypes, InternalEvent
from mirai.event.external.enums import ExternalEvents
from mirai.event.message import components
from mirai.event.message.models import (
    FriendMessage, GroupMessage, MessageItemType, MessageTypes)
from mirai.friend import Friend
from mirai.group import Group, Member
from mirai.logger import Event as EventLogger
from mirai.logger import Session as SessionLogger
from mirai.network import fetch, session
from mirai.protocol import MiraiProtocol
from mirai.event.message import MessageChain
import traceback

class Mirai(MiraiProtocol):
  event: Dict[
    str, List[Callable[[Any], Awaitable]]
  ] = {}
  run_forever_target: List[Callable] = []

  def __init__(self, 
    url: T.Optional[str] = None,

    host: T.Optional[str] = None,
    port: T.Optional[int] = None,
    authKey: T.Optional[str] = None,
    qq: T.Optional[int] = None
  ):
    if url:
      urlinfo = parse.urlparse(url)
      if urlinfo:
        query_info = parse.parse_qs(urlinfo.query)
        if all([
          urlinfo.scheme == "mirai",
          urlinfo.path == "/",

          "authKey" in query_info and query_info["authKey"],
          "qq" in query_info and query_info["qq"]
        ]):
          authKey = query_info["authKey"][0]

          self.baseurl = f"http://{urlinfo.netloc}"
          self.auth_key = authKey
          self.qq = query_info["qq"][0]
        else:
          raise ValueError("invaild url: wrong format")
      else:
        raise ValueError("invaild url")
    else:
      if all([host, port, authKey, qq]): 
        self.baseurl = f"http://{host}:{port}"
        self.auth_key = authKey
        self.qq = qq
      else:
        raise ValueError("invaild arguments")

  async def enable_session(self) -> "Session":
    auth_response = await super().auth()
    if all([
      "code" in auth_response and auth_response['code'] == 0,
      "session" in auth_response and auth_response['session']
    ]):
      if "msg" in auth_response and auth_response['msg']:
        self.session_key = auth_response['msg']
      else:
        self.session_key = auth_response['session']

      await super().verify()
    else:
      if "code" in auth_response and auth_response['code'] == 1:
        raise ValueError("invaild authKey")
      else:
        raise ValueError('invaild args: unknown response')

    self.enabled = True
    return self

  def receiver(self, event_name,
      dependencies: T.List[Depend] = [],
      use_middlewares: T.List[T.Callable] = []
    ):
    def receiver_warpper(
      func: T.Callable[[T.Union[FriendMessage, GroupMessage], "Session"], T.Awaitable[T.Any]]
    ):
      if not inspect.iscoroutinefunction(func):
        raise TypeError("event body must be a coroutine function.")

      protocol = {
        "func": func,
        "dependencies": dependencies,
        "middlewares": use_middlewares
      }
      
      if event_name not in self.event:
        self.event[event_name] = [protocol]
      else:
        self.event[event_name].append(protocol)
      return func
    return receiver_warpper

  async def throw_exception_event(self, event_context, queue, exception):
    if event_context.name != "UnexpectedException":
      #print("error: by pre:", event_context.name)
      await queue.put(InternalEvent(
        name="UnexpectedException",
        body=UnexpectedException(
          error=exception,
          event=event_context,
          session=self
        )
      ))
      EventLogger.error(f"threw a exception by {event_context.name}, Exception: {exception}")
      traceback.print_exc()
    else:
      EventLogger.critical(f"threw a exception by {event_context.name}, Exception: {exception}, it's a exception handler.")

  async def argument_compiler(self, func, event_context):
    annotations_mapping = self.get_annotations_mapping()
    signature_mapping = self.signature_getter(func)
    translated_mapping = { # 执行主体
      k: annotations_mapping[v](
        event_context
      )\
      for k, v in func.__annotations__.items()\
        if \
          k != "return" and \
          k not in signature_mapping # 嗯...你设了什么default? 放你过去.
    }
    return translated_mapping

  def signature_getter(self, func):
    "获取函数的默认值列表"
    return {k: v.default \
      for k, v in dict(inspect.signature(func).parameters).items() \
        if v.default != inspect._empty}

  def signature_checker(self, func):
    signature_mapping = self.signature_getter(func)
    for i in signature_mapping.values():
      if not isinstance(i, Depend):
        raise TypeError("you must use a Depend to patch the default value.")

  async def signature_checkout(self, func, event_context, queue):
    signature_mapping = self.signature_getter(func)
    return {
      k: await self.main_entrance(
        v.func,
        event_context,
        queue
      ) for k, v in signature_mapping.items()
    }

  async def main_entrance(self, run_body, event_context, queue):
    if isinstance(run_body, dict):
      callable_target = run_body['func']
      for depend in run_body['dependencies']:
        if not inspect.isclass(depend.func):
          depend_func = depend.func
        elif hasattr(depend.func, "__call__"):
          depend_func = depend.func.__call__
        else:
          raise TypeError("must be callable.")

        await self.main_entrance(
          {
            "func": depend_func,
            "middlewares": depend.middlewares
          },
          event_context, queue
        )
    else:
      if inspect.isclass(run_body):
        if hasattr(run_body, "__call__"):
          run_body = run_body.__call__
        else:
          raise TypeError("must be callable.")
      else:
        callable_target = run_body

    translated_mapping = {
      **(await self.argument_compiler(
        callable_target,
        event_context
      )),
      **(await self.signature_checkout(
        callable_target,
        event_context,
        queue
      ))
    }

    try:
      if isinstance(run_body, dict):
        middlewares = run_body.get("middlewares")
        if middlewares:
          async_middlewares = []
          normal_middlewares = []

          for middleware in middlewares:
            if all([
              hasattr(middleware, "__aenter__"),
              hasattr(middleware, "__aexit__")
            ]):
              async_middlewares.append(middleware)
            elif all([
              hasattr(middleware, "__enter__"),
              hasattr(middleware, "__exit__")
            ]):
              normal_middlewares.append(middleware)
            else:
              SessionLogger.error(f"threw a exception by {event_context.name}, no currect context error.")
              raise AttributeError("no a currect context object.")

          async with contextlib.AsyncExitStack() as async_stack:
            for async_middleware in async_middlewares:
              SessionLogger.debug(f"a event called {event_context.name}, enter a currect async context.")
              await async_stack.enter_async_context(async_middleware)

            with contextlib.ExitStack() as normal_stack:
              for normal_middleware in normal_middlewares:
                SessionLogger.debug(f"a event called {event_context.name}, enter a currect context.")
                normal_stack.enter_context(normal_middleware)

              if inspect.iscoroutinefunction(callable_target):
                return await callable_target(**translated_mapping)
              else:
                return callable_target(**translated_mapping)
        else:
          if inspect.iscoroutinefunction(callable_target):
            return await callable_target(**translated_mapping)
          else:
            return callable_target(**translated_mapping)
      else:
        if inspect.iscoroutinefunction(callable_target):
          return await callable_target(**translated_mapping)
        else:
          return callable_target(**translated_mapping)
    except (NameError, TypeError) as e:
      EventLogger.error(f"threw a exception by {event_context.name}, it's about Annotations Checker, please report to developer.")
      traceback.print_exc()
    except Exception as e:
      EventLogger.error(f"threw a exception by {event_context.name}, and it's {e}")
      await self.throw_exception_event(event_context, queue, e)

  async def message_polling(self, exit_signal, queue, count=10):
    while not exit_signal():
      await asyncio.sleep(0.5)

      result  = \
        await super().fetchMessage(count)
      last_length = len(result)
      latest_result = []
      while True:
        if last_length == count:
          latest_result = await super().fetchMessage(count)
          last_length = len(latest_result)
          result += latest_result
          continue
        break

      for message_index in range(len(result)):
        item = result[message_index]
        await queue.put(
          InternalEvent(
            name=self.getEventCurrentName(type(item)),
            body=item
          )
        )
  
  async def event_runner(self, exit_signal_status, queue: asyncio.Queue):
    while not exit_signal_status():
      event_context: InternalEvent
      try:
        event_context: T.NamedTuple[InternalEvent] = await asyncio.wait_for(queue.get(), 3)
      except asyncio.TimeoutError:
        if exit_signal_status():
          break
        else:
          continue

      if event_context.name in self.registeredEventNames:
        for event_body in list(self.event.values())\
              [self.registeredEventNames.index(event_context.name)]:
          if event_body:
            EventLogger.info(f"handling a event: {event_context.name}, on {event_body}")

            asyncio.create_task(self.main_entrance(
              event_body,
              event_context, queue
            ))
  
  def getRestraintMapping(self):
    def warpper(name, event_context):
      return name == event_context.name
    return {
      Mirai: lambda k: True,
      GroupMessage: lambda k: k.name == "GroupMessage",
      FriendMessage: lambda k: k.name =="FriendMessage",
      MessageChain: lambda k: k.name in MessageTypes,
      components.Source: lambda k: k.name in MessageTypes,
      Group: lambda k: k.name == "GroupMessage",
      Friend: lambda k: k.name =="FriendMessage",
      Member: lambda k: k.name == "GroupMessage",
      "Sender": lambda k: k.name in MessageTypes,
      "Type": lambda k: k.name,
      **({
        event_class.value: partial(warpper, copy.copy(event_name))
        for event_name, event_class in \
          ExternalEvents.__members__.items()
      })
    }

  def checkEventBodyAnnotations(self):
    event_bodys: T.Dict[T.Callable, T.List[str]] = {}
    for event_name in self.event:
      event_body_list = sum([list(i.values()) for i in self.event[event_name]], [])
      for i in event_body_list:
        if not event_bodys.get(i['func']):
          event_bodys[i['func']] = [event_name]
        else:
          event_bodys[i['func']].append(event_name)
    
    restraint_mapping = self.getRestraintMapping()
    
    for func in event_bodys:
      whileList = self.signature_getter(func)
      for param_name, func_item in func.__annotations__.items():
        if param_name not in whileList:
          for event_name in event_bodys[func]:
            try:
              if not (restraint_mapping[func_item](
                  type("checkMockType", (object,), {
                    "name": event_name
                  })
                )
              ):
                raise ValueError(f"error in annotations checker: {func}.{func_item}: {event_name}")
            except KeyError:
              raise ValueError(f"error in annotations checker: {func}.{func_item} is invaild.")
            except ValueError:
              raise

  def checkEventDependencies(self):
    for event_name, event_bodys in self.event.items():
      for i in event_bodys:
        value = list(i.values())[0]
        for depend in value['dependencies']:
          if type(depend) != Depend:
            raise TypeError(f"error in dependencies checker: {value['func']}: {event_name}")

  def exception_handler(self, exception_class=None, addon_condition=None):
    return self.receiver("UnexpectedException",
      lambda context: True \
        if not exception_class else \
          type(context.error) == exception_class and (
            addon_condition(context) \
              if addon_condition else True
          )
    )

  def gen_event_anno(self):
    result = {}
    for event_name, event_class in ExternalEvents.__members__.items():
      def warpper(name, event_context):
        if name != event_context.name:
          raise ValueError("cannot look up a non-listened event.")
        return event_context.body
      result[event_class.value] = partial(warpper, copy.copy(event_name))
    return result

  def get_annotations_mapping(self):
    return {
      Mirai: lambda k: self,
      GroupMessage: lambda k: k.body \
        if k.name == "GroupMessage" else\
          raiser(ValueError("you cannot setting a unbind argument.")),
      FriendMessage: lambda k: k.body \
        if k.name == "FriendMessage" else\
          raiser(ValueError("you cannot setting a unbind argument.")),
      MessageChain: lambda k: k.body.messageChain\
        if k.name in MessageTypes else\
          raiser(ValueError("MessageChain is not enable in this type of event.")),
      components.Source: lambda k: k.body.messageChain.getSource()\
        if k.name in MessageTypes else\
          raiser(TypeError("Source is not enable in this type of event.")),
      Group: lambda k: k.body.sender.group\
        if k.name == "GroupMessage" else\
          raiser(ValueError("Group is not enable in this type of event.")),
      Friend: lambda k: k.body.sender\
        if k.name == "FriendMessage" else\
          raiser(ValueError("Friend is not enable in this type of event.")),
      Member: lambda k: k.body.sender\
        if k.name == "GroupMessage" else\
          raiser(ValueError("Group is not enable in this type of event.")),
      "Sender": lambda k: k.body.sender\
        if k.name in MessageTypes else\
          raiser(ValueError("Sender is not enable in this type of event.")),
      "Type": lambda k: k.name,
      **self.gen_event_anno()
    }

  def getEventCurrentName(self, event_value):
    from .event.builtins import UnexpectedException
    if inspect.isclass(event_value) and issubclass(event_value, ExternalEvent): # subclass
      return event_value.__name__
    elif isinstance(event_value, ( # normal class
      UnexpectedException,
      GroupMessage,
      FriendMessage
    )):
      return event_value.__name__
    elif event_value in [ # message
      GroupMessage,
      FriendMessage
    ]:
      return event_value.__name__
    elif isinstance(event_value, ( # enum
      MessageItemType,
      ExternalEvents
    )):
      return event_value.name
    else:
      return event_value

  @property
  def registeredEventNames(self):
    return [self.getEventCurrentName(i) for i in self.event.keys()]

  def addForeverTarget(self, func: Callable[["Mirai"], Any]):
    self.run_forever_target.append(func)

  def run(self, loop=None):
    loop = loop or asyncio.get_event_loop()
    queue = asyncio.Queue(loop=loop)
    exit_signal = False
    loop.run_until_complete(self.enable_session())
    loop.create_task(self.message_polling(lambda: exit_signal, queue))
    loop.create_task(self.event_runner(lambda: exit_signal, queue))
    for i in self.run_forever_target:
      loop.create_task(i(self))

    try:
      loop.run_forever()
    except KeyboardInterrupt:
      SessionLogger.info("catched Ctrl-C, exiting..")
    finally:
      loop.run_until_complete(self.release())
      loop.run_until_complete(session.close())
