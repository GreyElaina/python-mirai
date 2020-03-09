from mirai import Mirai, Image, Plain, MessageChain, Group
import asyncio

authKey = "213we355gdfbaerg"
qq = 208924405

app = Mirai(f"mirai://localhost:8070/?authKey={authKey}&qq={qq}")

@app.receiver("GroupMessage")
async def event_gm(app: Mirai, message: MessageChain, group: Group):
    if message.toString().startswith("/image"):
        await app.sendGroupMessage(group, [
            Image.fromFileSystem("E:\\Image\\00C49FCD-D8D9-4966-B2FC-F18F6220485E.jpg"),
            Plain(text="??")
        ])

@app.addForeverTarget
async def forever_target(app: Mirai):
    pass

if __name__ == "__main__":
    print(app.baseurl)
    app.run()