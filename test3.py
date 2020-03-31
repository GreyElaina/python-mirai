from pydantic import BaseModel
from devtools import debug
from mirai.misc import printer
from collections import namedtuple
import inspect

Parameter = namedtuple("Parameter", ["name", "annotation", "default"])

def argument_signature(callable_target):
    return [
        Parameter(
            name=name,
            annotation=param.annotation if param.annotation != inspect._empty else None,
            default=param.default if param.default != inspect._empty else None
        )
        for name, param in dict(inspect.signature(callable_target).parameters).items()
    ]

def u(r):
    pass

debug(argument_signature(u))
#debug(dict(inspect.signature(u).parameters)['r'].empty)