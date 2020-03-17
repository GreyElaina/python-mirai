from mirai import Mirai, Image, Plain, MessageChain, Group, Member, Depend
import asyncio
from devtools import debug

authKey = "213we355gdfbaerg"
qq = 208924405

app = Mirai(f"mirai://localhost:8070/?authKey={authKey}&qq={qq}", websocket=True)

@app.receiver("GroupMessage")
async def event_gm(app: Mirai, message: MessageChain, group: Group, member: Member):
    if group.id == 655057127 and member.id == 1846913566:
        await app.sendGroupMessage(
            group,
            [
                Image.fromFileSystem("E:\\Image\\2D90645B-B807-4A7B-9E15-4FFA21562E4D.jpg")
            ]
        )

if __name__ == "__main__":
    app.run()