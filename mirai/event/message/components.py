from enum import Enum
import typing as T
from uuid import UUID
from mirai.misc import findKey, printer, ImageRegex, getMatchedString, randomRangedNumberString as rd
from mirai.face import QQFaces
from mirai.event.message.base import BaseMessageComponent, MessageComponentTypes
from pydantic import Field, validator, HttpUrl
from pydantic.generics import GenericModel
from mirai.network import fetch, session
from mirai.misc import ImageType
from io import BytesIO
from pathlib import Path
from mirai.image import InternalImage
import datetime
import re

__all__ = [
    "Plain",
    "Source",
    "At",
    "AtAll",
    "Face",
    "Image",
    "Unknown",
    "Quote"
]

class Plain(BaseMessageComponent):
    type: MessageComponentTypes = "Plain"
    text: str

    def __init__(self, text, type="Plain"):
        super().__init__(text=text, type="Plain")

    def toString(self):
        return self.text

class Source(BaseMessageComponent):
    type: MessageComponentTypes = "Source"
    id: int
    time: datetime.datetime

    def toString(self):
        return ""

from .chain import MessageChain

class Quote(BaseMessageComponent):
    type: MessageComponentTypes = "Quote"
    id: T.Optional[int]
    groupId: T.Optional[int]
    senderId: T.Optional[int]
    origin: MessageChain

    @validator("origin", always=True, pre=True)
    @classmethod
    def origin_formater(cls, v):
        return MessageChain.parse_obj(v)

    def __init__(self, id: int, groupId: int, senderId: int, origin: int, type="Quote"):
        super().__init__(
            id=id,
            groupId=groupId,
            senderId=senderId,
            origin=origin,
            type="Quote"
        )

    def toString(self):
        return ""

class At(BaseMessageComponent):
    type: MessageComponentTypes = "At"
    target: int
    display: T.Optional[str] = None

    def __init__(self, target, display=None, type="At"):
        super().__init__(target=target, display=display, type=type)

    def toString(self):
        return f"[At::target={self.target}]"

class AtAll(BaseMessageComponent):
    type: MessageComponentTypes = "AtAll"

    def __init__(self, type="AtAll"):
        super().__init__(type="AtAll")

    def toString(self):
        return f"[AtAll]"

class Face(BaseMessageComponent):
    type: MessageComponentTypes = "Face"
    faceId: int
    name: T.Optional[str]

    def __init__(self, faceId, name=None, type="Face"):
        super().__init__(faceId=faceId, name=name, type=type)

    def toString(self):
        return f"[Face::name={self.name}]"

class Image(BaseMessageComponent):
    type: MessageComponentTypes = "Image"
    imageId: str
    url: T.Optional[HttpUrl] = None

    @validator("imageId", always=True, pre=True)
    @classmethod
    def imageId_formater(cls, v):
        length = len(v)
        if length == 42:
            # group
            return v[1:-5]
        elif length == 37:
            return v[1:]
        else:
            return v

    def __init__(self, imageId, url=None, type="Image"):
        super().__init__(imageId=imageId, url=url, type="Image")

    def toString(self):
        return f"[Image::{self.imageId}]"

    def asGroupImage(self) -> str:
        return f"{{{self.imageId.upper()}}}.jpg"

    def asFriendImage(self) -> str:
        return f"/{self.imageId.lower()}"

    @staticmethod
    def fromFileSystem(path: T.Union[Path, str]) -> InternalImage:
        return InternalImage(path)

    async def toBytes(self, chunk_size=256) -> BytesIO:
        async with session.get(self.url) as response:
            result = BytesIO()
            while True:
                chunk = await response.content.read(chunk_size)
                if not chunk:
                    break
                result.write(chunk)
        return result

class Xml(BaseMessageComponent):
    type: MessageComponentTypes = "Xml"
    XML: str

    def __init__(self, xml, type="Xml"):
        super().__init__(XML=xml)

class Json(BaseMessageComponent):
    type: MessageComponentTypes = "Json"
    Json: dict = Field(..., alias="json")

    def __init__(self, json: dict, type="Json"):
        super().__init__(Json=json)

class App(BaseMessageComponent):
    type: MessageComponentTypes = "App"
    content: str

    def __init__(self, content: str, type="App"):
        super().__init__(content=content)

class Unknown(BaseMessageComponent):
    type: MessageComponentTypes = "Unknown"
    text: str

    def toString(self):
        return ""

MessageComponents = {
    "At": At,
    "AtAll": AtAll,
    "Face": Face,
    "Plain": Plain,
    "Image": Image,
    "Source": Source,
    "Quote": Quote,
    "Xml": Xml,
    "Json": Json,
    "App": App,
    "Unknown": Unknown
}