from . import InternalEvent
from pydantic import BaseModel
from typing import Any

class UnexpectedException(BaseModel):
    error: Exception
    event: InternalEvent
    application: Any

    class Config:
        arbitrary_types_allowed = True