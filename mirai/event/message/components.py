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

    def __init__(self, text):
        super().__init__(text=text)

    def toString(self):
        return self.text

class Source(BaseMessageComponent):
    type: MessageComponentTypes = "Source"
    id: int
    time: datetime.datetime

    def toString(self):
        return ""

class Quote(BaseMessageComponent):
    type: MessageComponentTypes = "Quote"
    id: int

    def toString(self):
        return ""

class At(BaseMessageComponent):
    type: MessageComponentTypes = "At"
    target: int
    display: T.Optional[str] = None

    def __init__(self, target, display=None):
        super().__init__(target=target, display=display)

    def toString(self):
        return f"[At::target={self.target}]"

class AtAll(BaseMessageComponent):
    type: MessageComponentTypes = "AtAll"

    def toString(self):
        return f"[AtAll]"

class Face(BaseMessageComponent):
    type: MessageComponentTypes = "Face"
    faceId: int

    def __init__(self, faceId):
        super().__init__(faceId=faceId)

    def toString(self):
        return f"[Face::key={findKey(QQFaces, self.faceId)}]"

class Image(BaseMessageComponent):
    type: MessageComponentTypes = "Image"
    imageId: UUID
    url: T.Optional[HttpUrl] = None

    def __init__(self, imageId):
        super().__init__(imageId=imageId)

    @validator("imageId", always=True, pre=True)
    @classmethod
    def imageId_formater(cls, v):
        if isinstance(v, str):
            imageType = "group"
            uuid_string = getMatchedString(re.search(ImageRegex[imageType], v))
            if not uuid_string:
                imageType = "friend"
                uuid_string = getMatchedString(re.search(ImageRegex[imageType], v))
            if uuid_string:
                return UUID(uuid_string)
        elif isinstance(v, UUID):
            return v

    def toString(self):
        return f"[Image::{self.imageId}]"

    def asGroupImage(self) -> str:
        return f"{{{str(self.imageId).upper()}}}.jpg"

    def asFriendImage(self) -> str:
        return f"/{str(self.imageId)}"

    @staticmethod
    def fromFileSystem(path: T.Union[Path, str]) -> InternalImage:
        return InternalImage(path)

class Unknown(BaseMessageComponent):
    type: MessageComponentTypes = "Unknown"
    text: str

    def toString(self):
        return ""

class ComponentTypes(Enum):
    Plain = Plain
    Source = Source
    At = At
    AtAll = AtAll
    Face = Face
    Image = Image
    Quote = Quote
    Unknown = Unknown

MessageComponents = {
    "At": At,
    "AtAll": AtAll,
    "Face": Face,
    "Plain": Plain,
    "Image": Image,
    "Source": Source,
    "Quote": Quote,
    "Unknown": Unknown
}