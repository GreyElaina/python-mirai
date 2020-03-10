from mirai import Mirai, Image, Plain, MessageChain, Group, Member, Depend
import asyncio

authKey = "213we355gdfbaerg"
qq = 208924405

app = Mirai(f"mirai://localhost:8070/ws?authKey={authKey}&qq={qq}")

async def depend2(message: MessageChain):
    print(message.toString())

async def depend1(m: str = Depend(depend2)):
    pass

@app.receiver("GroupMessage", dependencies=[Depend(depend1)])
async def event_gm(app: Mirai, message: MessageChain, group: Group, member: Member):
    if message.toString().startswith("色图"):
        await app.sendGroupMessage(group, [
            Plain(text="没有色图 快滚.")
        ])

@app.addForeverTarget
async def forever_target(app: Mirai):
    pass

if __name__ == "__main__":
    app.run()