import asyncio
import copy
import inspect
import traceback
from functools import partial
from typing import (
    Any, Awaitable, Callable, Dict, List, NamedTuple, Optional, Union)
from urllib import parse
import contextlib

import pydantic
import aiohttp

from mirai.depend import Depend
from mirai.entities.friend import Friend
from mirai.entities.group import Group, Member
from mirai.event import ExternalEvent, ExternalEventTypes, InternalEvent
from mirai.event.message import MessageChain, components
from mirai.event.message.models import (FriendMessage, GroupMessage,
                                        MessageItemType, MessageTypes)
from mirai.logger import Event as EventLogger
from mirai.logger import Session as SessionLogger
from mirai.misc import raiser, TRACEBACKED
from mirai.network import fetch
from mirai.protocol import MiraiProtocol
from mirai.exceptions import Cancelled

class Mirai(MiraiProtocol):
  event: Dict[
    str, List[Callable[[Any], Awaitable]]
  ] = {}
  subroutines: List[Callable] = []
  lifecycle: Dict[str, List[Callable]] = {
    "start": [],
    "end": [],
    "around": []
  }
  useWebsocket = False
  listening_exceptions: List[Exception] = []
  extensite_config: Dict
  global_dependencies: List[Depend]

  def __init__(self,
    url: Optional[str] = None,

    host: Optional[str] = None,
    port: Optional[int] = None,
    authKey: Optional[str] = None,
    qq: Optional[int] = None,

    websocket: bool = False,
    extensite_config: dict = None,
    global_dependencies: List[Depend] = None
  ):
    self.extensite_config = extensite_config or {}
    self.global_dependencies = global_dependencies or []
    self.useWebsocket = websocket
    if url:
      urlinfo = parse.urlparse(url)
      if urlinfo:
        query_info = parse.parse_qs(urlinfo.query)
        if all([
          urlinfo.scheme == "mirai",
          urlinfo.path in ["/", "/ws"],

          "authKey" in query_info and query_info["authKey"],
          "qq" in query_info and query_info["qq"]
        ]):
          if urlinfo.path == "/ws":
            self.useWebsocket = True
          else:
            self.useWebsocket = websocket

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
    auth_response = await self.auth()
    if all([
      "code" in auth_response and auth_response['code'] == 0,
      "session" in auth_response and auth_response['session']
    ]):
      if "msg" in auth_response and auth_response['msg']:
        self.session_key = auth_response['msg']
      else:
        self.session_key = auth_response['session']

      await self.verify()
    else:
      if "code" in auth_response and auth_response['code'] == 1:
        raise ValueError("invaild authKey")
      else:
        raise ValueError('invaild args: unknown response')

    self.enabled = True
    return self

  def receiver(self, event_name,
      dependencies: List[Depend] = None,
      use_middlewares: List[Callable] = None
    ):
    def receiver_warpper(
      func: Callable[[Union[FriendMessage, GroupMessage], "Session"], Awaitable[Any]]
    ):
      if not inspect.iscoroutinefunction(func):
        raise TypeError("event body must be a coroutine function.")

      protocol = {
        "func": func,
        "dependencies": dependencies or [],
        "middlewares": use_middlewares or []
      }

      protocol['dependencies'] += self.global_dependencies
      # support for global dependencies
      
      if event_name not in self.event:
        self.event[event_name] = [protocol]
      else:
        self.event[event_name].append(protocol)
      return func
    return receiver_warpper

  async def throw_exception_event(self, event_context, queue, exception):
    from .event.builtins import UnexpectedException
    if event_context.name != "UnexpectedException":
      #print("error: by pre:", event_context.name)
      await queue.put(InternalEvent(
        name="UnexpectedException",
        body=UnexpectedException(
          error=exception,
          event=event_context,
          application=self
        )
      ))
      EventLogger.error(f"threw a exception by {event_context.name}, Exception: {exception.__class__.__name__}, but it has been catched.")
    else:
      EventLogger.critical(f"threw a exception by {event_context.name}, Exception: {exception.__class__.__name__}, it's a exception handler.")

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

  @staticmethod
  def signature_getter(func):
    "获取函数的默认值列表"
    return {k: v.default \
      for k, v in dict(inspect.signature(func).parameters).items() \
        if v.default != inspect._empty}

  @staticmethod
  def signature_checker(func):
    signature_mapping = Mirai.signature_getter(func)
    for i in signature_mapping.values():
      if not isinstance(i, Depend):
        raise TypeError("you must use a Depend to patch the default value.")
    return signature_mapping

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
        
        try:
          result = await self.main_entrance(
            {
              "func": depend_func,
              "middlewares": depend.middlewares,
              "dependencies": []
            },
            event_context, queue
          )
          if result is TRACEBACKED:
            return TRACEBACKED
        except Cancelled:
          return TRACEBACKED
        except (NameError, TypeError) as e:
          EventLogger.error(f"threw a exception by {event_context.name}, it's about Annotations Checker, please report to developer.")
          traceback.print_exc()
        except Exception as e:
          if type(e) not in self.listening_exceptions:
            EventLogger.error(f"threw a exception by {event_context.name} in a depend, and it's {e}, body has been cancelled.")
            raise
          else:
            await self.throw_exception_event(event_context, queue, e)
            return TRACEBACKED

    else:
      if inspect.isclass(run_body):
        if hasattr(run_body, "__call__"):
          run_body = run_body.__call__
        else:
          raise TypeError("must be callable.")
      else:
        callable_target = run_body

    depend_handler_result = await self.signature_checkout(
      callable_target,
      event_context,
      queue
    )
    if depend_handler_result is TRACEBACKED:
      return TRACEBACKED

    translated_mapping = {
      **(await self.argument_compiler(
        callable_target,
        event_context
      )),
      **depend_handler_result
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
    except Cancelled:
      return TRACEBACKED
    except Exception as e:
      if type(e) not in self.listening_exceptions:
        EventLogger.error(f"threw a exception by {event_context.name}, and it's {e}")
        raise
      else:
        await self.throw_exception_event(event_context, queue, e)
        return TRACEBACKED

  async def message_polling(self, exit_signal, queue, count=10):
    while not exit_signal():
      await asyncio.sleep(0.5)

      try:
        result  = \
          await super().fetchMessage(count)
      except pydantic.ValidationError:
        continue
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

  async def ws_event_receiver(self, exit_signal, queue):
    from mirai.event.external.enums import ExternalEvents
    async with aiohttp.ClientSession() as session:
      async with session.ws_connect(
        f"{self.baseurl}/all?sessionKey={self.session_key}"
      ) as ws_connection:
        while not exit_signal():
          try:
            received_data = await ws_connection.receive_json()
          except TypeError:
            if not exit_signal():
              continue
            else:
              break
          if received_data:
            try:
              if received_data['type'] in MessageTypes:
                  if 'messageChain' in received_data: 
                    received_data['messageChain'] = \
                      MessageChain.parse_obj(received_data['messageChain'])

                  received_data = \
                    MessageTypes[received_data['type']].parse_obj(received_data)

              elif hasattr(ExternalEvents, received_data['type']):
                  # 判断当前项是否为 Event
                  received_data = \
                    ExternalEvents[received_data['type']]\
                      .value\
                      .parse_obj(received_data)
            except pydantic.ValidationError:
              SessionLogger.error(f"parse failed: {received_data}")
              traceback.print_exc()
            else:
              await queue.put(InternalEvent(
                name=self.getEventCurrentName(type(received_data)),
                body=received_data
              ))

  async def event_runner(self, exit_signal_status, queue: asyncio.Queue):
    while not exit_signal_status():
      event_context: InternalEvent
      try:
        event_context: NamedTuple[InternalEvent] = await asyncio.wait_for(queue.get(), 3)
      except asyncio.TimeoutError:
        if exit_signal_status():
          break
        else:
          continue

      if event_context.name in self.registeredEventNames:
        for event_body in list(self.event.values())\
              [self.registeredEventNames.index(event_context.name)]:
          if event_body:
            EventLogger.info(f"handling a event: {event_context.name}")

            running_loop = asyncio.get_running_loop()
            running_loop.create_task(self.main_entrance(
              event_body,
              event_context, queue
            ))
  
  def getRestraintMapping(self):
    from mirai.event.external.enums import ExternalEvents
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
    event_bodys: Dict[Callable, List[str]] = {}
    for event_name in self.event:
      event_body_list = self.event[event_name]
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

  def getFuncRegisteredEvents(self, callable_target: Callable):
    event_bodys: Dict[Callable, List[str]] = {}
    for event_name in self.event:
      event_body_list = sum([list(i.values()) for i in self.event[event_name]], [])
      for i in event_body_list:
        if not event_bodys.get(i['func']):
          event_bodys[i['func']] = [event_name]
        else:
          event_bodys[i['func']].append(event_name)
    return event_bodys.get(callable_target)

  def checkFuncAnnotations(self, callable_target: Callable):
    restraint_mapping = self.getRestraintMapping()
    whileList = self.signature_getter(callable_target)
    registered_events = self.getFuncRegisteredEvents(callable_target)
    for param_name, func_item in callable_target.__annotations__.items():
      if param_name not in whileList:
        if not registered_events:
          raise ValueError(f"error in annotations checker: {callable_target} is invaild.")
        for event_name in registered_events:
          try:
            if not (restraint_mapping[func_item](
                type("checkMockType", (object,), {
                  "name": event_name
                })
              )
            ):
              raise ValueError(f"error in annotations checker: {callable_target}.{func_item}: {event_name}")
          except KeyError:
            raise ValueError(f"error in annotations checker: {callable_target}.{func_item} is invaild.")
          except ValueError:
            raise

  def checkDependencies(self, depend_target: Depend):
    signature_mapping = self.signature_checker(depend_target.func)
    for k, v in signature_mapping.items():
      if type(v) == Depend:
        self.checkEventBodyAnnotations()
        self.checkDependencies(v)

  def checkEventDependencies(self):
    for event_name, event_bodys in self.event.items():
      for i in event_bodys:
        for depend in i['dependencies']:
          if type(depend) != Depend:
            raise TypeError(f"error in dependencies checker: {i['func']}: {event_name}")
          else:
            self.checkDependencies(depend)

  def exception_handler(self, exception_class=None):
    from .event.builtins import UnexpectedException
    from mirai.event.external.enums import ExternalEvents
    def receiver_warpper(
      func: Callable[[Union[FriendMessage, GroupMessage], "Session"], Awaitable[Any]]
    ):
      event_name = "UnexpectedException"

      if not inspect.iscoroutinefunction(func):
        raise TypeError("event body must be a coroutine function.")
    
      async def func_warpper_inout(context: UnexpectedException, *args, **kwargs):
        if type(context.error) == exception_class:
          return await func(context, *args, **kwargs)

      func_warpper_inout.__annotations__.update(func.__annotations__)

      protocol = {
        "func": func_warpper_inout,
        "dependencies": [],
        "middlewares": []
      }
      
      if event_name not in self.event:
        self.event[event_name] = [protocol]
      else:
        self.event[event_name].append(protocol)

      if exception_class:
        if exception_class not in self.listening_exceptions:
          self.listening_exceptions.append(exception_class)
      return func
    return receiver_warpper

  def gen_event_anno(self):
    from mirai.event.external.enums import ExternalEvents
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
    from mirai.event.external.enums import ExternalEvents
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

  def subroutine(self, func: Callable[["Mirai"], Any]):
    from .event.builtins import UnexpectedException
    async def warpper(app: "Mirai"):
      try:
        return await func(app)
      except Exception as e:
        await self.queue.put(InternalEvent(
          name="UnexpectedException",
          body=UnexpectedException(
            error=e,
            event=None,
            application=self
          )
        ))
    self.subroutines.append(warpper)
    return func

  async def checkWebsocket(self, force=False):
    return (await self.getConfig())["enableWebsocket"]

  @staticmethod
  async def run_func(func, *args, **kwargs):
    if inspect.iscoroutinefunction(func):
      await func(*args, **kwargs)
    else:
      func(*args, **kwargs)

  def onStage(self, stage_name):
    def warpper(func):
      self.lifecycle.setdefault(stage_name, [])
      self.lifecycle[stage_name].append(func)
      return func
    return warpper

  def include_others(self, *args: List["Mirai"]):
    for other in args:
      for event_name, items in other.event.items():
        if event_name in self.event:
          self.event[event_name] += items
        else:
          self.event[event_name] = items.copy()
      self.subroutines = other.subroutines
      for life_name, items in other.lifecycle:
        self.lifecycle[life_name] += items
      self.listening_exceptions += other.listening_exceptions

  def run(self, loop=None, no_polling=False, no_forever=False):
    self.checkEventBodyAnnotations()
    self.checkEventDependencies()

    loop = loop or asyncio.get_event_loop()
    self.queue = queue = asyncio.Queue(loop=loop)
    exit_signal = False
    loop.run_until_complete(self.enable_session())
    if not no_polling:
      # check ws status
      if self.useWebsocket:
        SessionLogger.info("event receive method: websocket")
      else:
        SessionLogger.info("event receive method: http polling")

      result = loop.run_until_complete(self.checkWebsocket())
      if not result: # we can use http, not ws.
        # should use http, but we can change it.
        if self.useWebsocket:
          SessionLogger.warning("catched wrong config: enableWebsocket=false, we will modify it on launch.")
          loop.run_until_complete(self.setConfig(enableWebsocket=True))
          loop.create_task(self.ws_event_receiver(lambda: exit_signal, queue))
        else:
          loop.create_task(self.message_polling(lambda: exit_signal, queue))
      else: # we can use websocket, it's fine
        if self.useWebsocket:
          loop.create_task(self.ws_event_receiver(lambda: exit_signal, queue))
        else:
          SessionLogger.warning("catched wrong config: enableWebsocket=true, we will modify it on launch.")
          loop.run_until_complete(self.setConfig(enableWebsocket=False))
          loop.create_task(self.message_polling(lambda: exit_signal, queue))
      loop.create_task(self.event_runner(lambda: exit_signal, queue))
    
    if not no_forever:
      for i in self.subroutines:
        loop.create_task(i(self))

    try:
      for start_callable in self.lifecycle['start']:
        loop.run_until_complete(self.run_func(start_callable, self))

      for around_callable in self.lifecycle['around']:
        loop.run_until_complete(self.run_func(around_callable, self))

      loop.run_forever()
    except KeyboardInterrupt:
      SessionLogger.info("catched Ctrl-C, exiting..")
    except Exception as e:
      traceback.print_exc()
    finally:
      for around_callable in self.lifecycle['around']:
        loop.run_until_complete(self.run_func(around_callable, self))

      for end_callable in self.lifecycle['end']:
        loop.run_until_complete(self.run_func(end_callable, self))

      loop.run_until_complete(self.release())