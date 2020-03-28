from mirai import Mirai, Image, Plain, MessageChain, Group, Member, Depend
import asyncio
from devtools import debug

from mirai.command import CommandManager, Command

authKey = "213we355gdfbaerg"
qq = 208924405

app = Mirai(f"mirai://localhost:8070/?authKey={authKey}&qq={qq}", websocket=True)
cm = CommandManager(app, command_prefix=".")

@cm.Mark("test {na:Image} fq")
async def t(app: Mirai, na):
    pass

@app.receiver("GroupMessage")
async def event_gm(app: Mirai, message: MessageChain, group: Group, member: Member):
    pass

if __name__ == "__main__":
    app.run()