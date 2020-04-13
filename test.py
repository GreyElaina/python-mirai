from mirai import Mirai, Plain, MessageChain, Friend, Member, Group
import asyncio
from devtools import debug

qq = 208924405 # 字段 qq 的值
authKey = '213we355gdfbaerg' # 字段 authKey 的值
mirai_api_http_locate = 'localhost:8070/ws' # httpapi所在主机的地址端口,如果 setting.yml 文件里字段 "enableWebsocket" 的值为 "true" 则需要将 "/" 换成 "/ws", 否则将接收不到消息.

app = Mirai(f"mirai://{mirai_api_http_locate}?authKey={authKey}&qq={qq}")

@app.receiver("TempMessage")
async def event_tm(app: Mirai, group: Group, member: Member):
    debug(group, member)
    await app.sendTempMessage(group, member, [
        Plain(text="Hello, world, tempmessage")
    ])

@app.receiver("GroupMessage")
async def event_gm(app: Mirai, group: Group, member: Member):
    print(group, member)

if __name__ == "__main__":
    app.run()