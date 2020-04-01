from mirai import Mirai, Image, Plain, MessageChain, Group, Member, Depend, At, FriendMessage
import asyncio
from devtools import debug

from pprint import pprint
from mirai.command import CommandManager, Command
import random

authKey = "213we355gdfbaerg"
qq = 208924405

app = Mirai(f"mirai://localhost:8070/?authKey={authKey}&qq={qq}", websocket=True)

def depend1():
    print(1)
    return random.random()

def depend2(d = Depend(depend1)):
    print(2)
    return d

@app.receiver("GroupMessage")
async def event_gm(app: Mirai, message: MessageChain, group: Group, member: Member, d1 = Depend(depend1), d2 = Depend(depend2)):
    if member.id == 1846913566:
        m = message.getFirstComponent(Image)
        if m:
            await app.sendFriendMessage(member.id, [
                #Image.fromFileSystem("E:\\Image\\00C49FCD-D8D9-4966-B2FC-F18F6220485E.jpg")
                #At(target=1846913566)
                m
            ])

@app.receiver("FriendMessage")
async def R(app: Mirai, fm: FriendMessage):
    debug(fm)

if __name__ == "__main__":
    app.run()