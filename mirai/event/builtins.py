from . import InternalEvent

from mirai.session import Session
from pydantic import BaseModel

class UnexceptedException(BaseModel):
    error: Exception
    event: InternalEvent
    session: Session

    class Config:
        arbitrary_types_allowed = True