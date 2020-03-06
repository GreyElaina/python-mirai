import re
import typing as T
from datetime import timedelta
from pathlib import Path
from uuid import UUID
import json

from mirai.event.message.models import FriendMessage, GroupMessage, BotMessage, MessageTypes

from mirai.event import ExternalEvent
from mirai.event.external.enums import ExternalEvents
from mirai.friend import Friend
from mirai.group import Group, GroupSetting, Member, MemberChangeableSetting
from mirai.event.message.chain import MessageChain
from mirai.misc import ImageRegex, ImageType, assertOperatorSuccess, raiser, printer, getMatchedString
from mirai.network import fetch
from mirai.event.message.base import BaseMessageComponent
from mirai.event.message import components
from mirai.misc import protocol_log
from mirai.image import InternalImage
import threading

class MiraiProtocol:
    qq: int
    baseurl: str
    session_key: str
    auth_key: str

    @protocol_log
    async def auth(self):
        return assertOperatorSuccess(
            await fetch.http_post(f"{self.baseurl}/auth", {
                "authKey": self.auth_key
            }
        ), raise_exception=True, return_as_is=True)

    @protocol_log
    async def verify(self):
        return assertOperatorSuccess(
            await fetch.http_post(f"{self.baseurl}/verify", {
                "sessionKey": self.session_key,
                "qq": self.qq
            }
        ), raise_exception=True, return_as_is=True)

    @protocol_log
    async def release(self):
        return assertOperatorSuccess(
            await fetch.http_post(f"{self.baseurl}/release", {
                "sessionKey": self.session_key,
                "qq": self.qq
            }
        ), raise_exception=True)

    @protocol_log
    async def sendFriendMessage(self,
        friend: T.Union[Friend, int],
        message: T.Union[
            MessageChain,
            BaseMessageComponent,
            T.List[BaseMessageComponent],
            str
        ]
    ) -> BotMessage:
        return BotMessage.parse_obj(assertOperatorSuccess(
            await fetch.http_post(f"{self.baseurl}/sendFriendMessage", {
                "sessionKey": self.session_key,
                "target": self.handleTargetAsFriend(friend),
                "messageChain": await self.handleMessageAsFriend(message)
            }
        ), raise_exception=True, return_as_is=True))
    
    @protocol_log
    async def sendGroupMessage(self,
        group: T.Union[Group, int],
        message: T.Union[
            MessageChain,
            BaseMessageComponent,
            T.List[BaseMessageComponent],
            str
        ],
        quoteSource: T.Union[int, components.Source]=None
    ) -> BotMessage:
        return BotMessage.parse_obj(assertOperatorSuccess(
            await fetch.http_post(f"{self.baseurl}/sendGroupMessage", {
                "sessionKey": self.session_key,
                "target": self.handleTargetAsGroup(group),
                "messageChain": await self.handleMessageAsGroup(message),
                **({"quote": quoteSource.id \
                    if isinstance(quoteSource, components.Source) else quoteSource}\
                if quoteSource else {})
            }
        ), raise_exception=True, return_as_is=True))

    @protocol_log
    async def revokeMessage(self, source: T.Union[components.Source, int]):
        return assertOperatorSuccess(await fetch.http_post(f"{self.baseurl}/recall", {
            "sessionKey": self.session_key,
            "target": source if isinstance(source, int) else source.id
        }), raise_exception=True)

    @protocol_log
    async def groupList(self) -> T.List[Group]:
        return [Group.parse_obj(group_info) \
            for group_info in await fetch.http_get(f"{self.baseurl}/groupList", {
                "sessionKey": self.session_key
            })
        ]

    @protocol_log
    async def friendList(self) -> T.List[Friend]:
        return [Friend.parse_obj(friend_info) \
            for friend_info in await fetch.http_get(f"{self.baseurl}/friendList", {
                "sessionKey": self.session_key
            })
        ]

    @protocol_log
    async def memberList(self, target: int) -> T.List[Member]:
        return [Member.parse_obj(member_info) \
            for member_info in await fetch.http_get(f"{self.baseurl}/memberList", {
                "sessionKey": self.session_key,
                "target": target
            })
        ]

    @protocol_log
    async def groupMemberNumber(self, target: int) -> int:
        return len(await self.memberList(target)) + 1

    @protocol_log
    async def uploadImage(self, type: T.Union[str, ImageType], imagePath: T.Union[Path, str]):
        if isinstance(imagePath, str):
            imagePath = Path(imagePath)

        if not imagePath.exists():
            raise FileNotFoundError("invaild image path.")

        post_result = json.loads(printer(await fetch.upload(f"{self.baseurl}/uploadImage", imagePath, {
            "sessionKey": self.session_key,
            "type": type if isinstance(type, str) else type.value
        })))
        return components.Image(**post_result)

    async def fetchMessage(self, count: int) -> T.List[T.Union[FriendMessage, GroupMessage, ExternalEvent]]:
        result = assertOperatorSuccess(
            await fetch.http_get(f"{self.baseurl}/fetchMessage", {
                "sessionKey": self.session_key,
                "count": count
            }
        ), raise_exception=True, return_as_is=True)
        # 因为重新生成一个开销太大, 所以就直接在原数据内进行遍历替换
        for index in range(len(result)):
            # 判断当前项是否为 Message
            if result[index]['type'] in MessageTypes:
                # 使用 custom_parse 方法处理消息链
                if 'messageChain' in result[index]: 
                    result[index]['messageChain'] = MessageChain.custom_parse(result[index]['messageChain'])

                result[index] = \
                    MessageTypes[result[index]['type']].parse_obj(result[index])
    
            elif hasattr(ExternalEvents, result[index]['type']):
                # 判断当前项是否为 Event
                result[index] = \
                    ExternalEvents[result[index]['type']].value.parse_obj(result[index])
        return result

    @protocol_log
    async def messageFromId(self, sourceId: T.Union[components.Source, components.Quote, int]):
        if isinstance(sourceId, (components.Source, components.Quote)):
            sourceId = sourceId.id

        result = assertOperatorSuccess(await fetch.http_get(f"{self.baseurl}/messageFromId", {
            "sessionKey": self.session_key,
            "id": sourceId
        }), raise_exception=True, return_as_is=True)

        if result['type'] in MessageTypes:
            if "messageChain" in result:
                result['messageChain'] = MessageChain.custom_parse(result['messageChain'])

            return MessageTypes[result['type']].parse_obj(result)
        else:
            raise TypeError(f"unknown message, not found type.")

    @protocol_log
    async def muteAll(self, group: T.Union[Group, int]) -> bool:
        return assertOperatorSuccess(
            await fetch.http_post(f"{self.baseurl}/muteAll", {
                "sessionKey": self.session_key,
                "target": self.handleTargetAsGroup(group)
            }
        ), raise_exception=True)
        
    @protocol_log
    async def unmuteAll(self, group: T.Union[Group, int]) -> bool:
        return assertOperatorSuccess(
            await fetch.http_post(f"{self.baseurl}/unmuteAll", {
                "sessionKey": self.session_key,
                "target": self.handleTargetAsGroup(group)
            }
        ), raise_exception=True)
    
    @protocol_log
    async def memberInfo(self,
        group: T.Union[Group, int],
        member: T.Union[Member, int]
    ):
        return MemberChangeableSetting.parse_obj(assertOperatorSuccess(
            await fetch.http_get(f"{self.baseurl}/memberInfo", {
                "sessionKey": self.session_key,
                "target": self.handleTargetAsGroup(group),
                "memberId": self.handleTargetAsMember(member)
            }
        ), raise_exception=True, return_as_is=True))

    @protocol_log
    async def botMemberInfo(self,
        group: T.Union[Group, int]
    ):
        return await self.memberInfo(group, self.qq)

    @protocol_log
    async def changeMemberInfo(self,
        group: T.Union[Group, int],
        member: T.Union[Member, int],
        setting: MemberChangeableSetting
    ) -> bool:
        return assertOperatorSuccess(
            await fetch.http_post(f"{self.baseurl}/memberInfo", {
                "sessionKey": self.session_key,
                "target": self.handleTargetAsGroup(group),
                "memberId": self.handleTargetAsMember(member),
                "info": json.loads(setting.json())
            }
        ), raise_exception=True)

    @protocol_log
    async def groupConfig(self, group: T.Union[Group, int]) -> GroupSetting:
        return GroupSetting.parse_obj(
            await fetch.http_get(f"{self.baseurl}/groupConfig", {
                "sessionKey": self.session_key,
                "target": self.handleTargetAsGroup(group)
            })
        )

    @protocol_log
    async def changeGroupConfig(self,
        group: T.Union[Group, int],
        config: GroupSetting
    ) -> bool:
        return assertOperatorSuccess(
            await fetch.http_post(f"{self.baseurl}/groupConfig", {
                "sessionKey": self.session_key,
                "target": self.handleTargetAsGroup(group),
                "config": json.loads(config.json())
            }
        ), raise_exception=True)

    @protocol_log
    async def mute(self,
        group: T.Union[Group, int],
        member: T.Union[Member, int],
        time: T.Union[timedelta, int]
    ):
        if isinstance(time, timedelta):
            time = int(time.total_seconds())
        time = min(86400 * 30, max(60, time))
        return assertOperatorSuccess(
            await fetch.http_post(f"{self.baseurl}/mute", {
                "sessionKey": self.session_key,
                "target": self.handleTargetAsGroup(group),
                "memberId": self.handleTargetAsMember(member),
                "time": time
            }
        ), raise_exception=True)

    @protocol_log
    async def unmute(self,
        group: T.Union[Group, int],
        member: T.Union[Member, int]
    ):
        return assertOperatorSuccess(
            await fetch.http_post(f"{self.baseurl}/unmute", {
                "sessionKey": self.session_key,
                "target": self.handleTargetAsGroup(group),
                "memberId": self.handleTargetAsMember(member),
            }
        ), raise_exception=True)

    @protocol_log
    async def kick(self,
        group: T.Union[Group, int],
        member: T.Union[Member, int],
        kickMessage: T.Optional[str] = None
    ):
        return assertOperatorSuccess(
            await fetch.http_post(f"{self.baseurl}/kick", {
                "sessionKey": self.session_key,
                "target": self.handleTargetAsGroup(group),
                "memberId": self.handleTargetAsMember(member),
                **({
                    "msg": kickMessage
                } if kickMessage else {})
            }
        ), raise_exception=True)

    async def handleMessageAsGroup(
        self,
        message: T.Union[
            MessageChain,
            BaseMessageComponent,
            T.List[BaseMessageComponent],
            str
        ]):
        if isinstance(message, MessageChain):
            return json.loads(message.json())
        elif isinstance(message, BaseMessageComponent):
            return [json.loads(message.json())]
        elif isinstance(message, (tuple, list)):
            result = []
            for i in message:
                if type(i) != InternalImage:
                    result.append(json.loads(i.json()))
                else:
                    result.append({
                        "type": "Image",
                        "imageId": (await self.handleInternalImageAsGroup(i)).asGroupImage()
                    })
            return result
        elif isinstance(message, str):
            return [json.loads(components.Plain(text=message).json())]
        else:
            raise raiser(ValueError("invaild message."))

    async def handleMessageAsFriend(
        self,
        message: T.Union[
            MessageChain,
            BaseMessageComponent,
            T.List[BaseMessageComponent],
            str
        ]):
        if isinstance(message, MessageChain):
            return json.loads(message.json())
        elif isinstance(message, BaseMessageComponent):
            return [json.loads(message.json())]
        elif isinstance(message, (tuple, list)):
            result = []
            for i in message:
                if type(i) != InternalImage:
                    result.append(json.loads(i.json()))
                else:
                    result.append({
                        "type": "Image",
                        "imageId": (await self.handleInternalImageAsFriend(i)).asFriendImage()
                    })
            return result
        elif isinstance(message, str):
            return [json.loads(components.Plain(text=message).json())]
        else:
            raise raiser(ValueError("invaild message."))

    def handleTargetAsGroup(self, target: T.Union[Group, int]):
        return target if isinstance(target, int) else \
            target.id if isinstance(target, Group) else \
                raiser(ValueError("invaild target as group."))

    def handleTargetAsFriend(self, target: T.Union[Friend, int]):
        return target if isinstance(target, int) else \
            target.id if isinstance(target, Friend) else \
                raiser(ValueError("invaild target as a friend obj."))

    def handleTargetAsMember(self, target: T.Union[Member, int]):
        return target if isinstance(target, int) else \
            target.id if isinstance(target, Member) else \
                raiser(ValueError("invaild target as a member obj."))

    async def handleInternalImageAsGroup(self, image: InternalImage):
        return await self.uploadImage("group", image.path)

    async def handleInternalImageAsFriend(self, image: InternalImage):
        return await self.uploadImage("friend", image.path)