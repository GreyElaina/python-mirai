from pathlib import Path
from abc import ABCMeta, abstractmethod
import base64

class InternalImage(metaclass=ABCMeta):
    @abstractmethod
    def __init__(self):
        super().__init__()

    @abstractmethod
    def render(self) -> bytes:
        pass

class LocalImage(InternalImage):
    path: Path

    def __init__(self, path):
        if isinstance(path, str):
            self.path = Path(path)
        elif isinstance(path, Path):
            self.path = path

    def render(self) -> bytes:
        return self.path.read_bytes()

class IOImage(InternalImage):
    def __init__(self, IO):
        """make a object with 'read' method a image.

        IO - a object, must has a `read` method to return bytes.
        """
        self.IO = IO

    def render(self) -> bytes:
        return self.IO.read()

class BytesImage(InternalImage):
    def __init__(self, data: bytes):
        self.data = data

    def render(self) -> bytes:
        return self.data

class Base64Image(InternalImage):
    def __init__(self, base64_str):
        self.base64_str = base64_str
    
    def render(self) -> bytes:
        return base64.b64decode(self.base64_str)