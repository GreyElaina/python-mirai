from mirai import Mirai, Image, Plain, MessageChain, Group, Member, Depend
import asyncio
from devtools import debug

authKey = "213we355gdfbaerg"
qq = 208924405

app = Mirai(f"mirai://localhost:8070/ws?authKey={authKey}&qq={qq}")

@app.receiver("GroupMessage")
async def event_gm(app: Mirai, message: MessageChain, group: Group, member: Member):
    debug(message)

{'type': 'GroupMessage', 'messageChain': [{'type': 'Source', 'id': 3755531209654991, 'time': 1584024199}, {'type': 'At', 'target': 1924257498, 'display': '@幼天使珈百璃٩(ˊ〇ˋ*)و'}, {'type': 'Plain', 'text': ' '}, {'type': 'Quote', 'id': 3755467517902601, 'groupId': 819397581, 'senderId': 1924257498, 'origin': [{'type': 'Source', 'id': 3755467517902601, 'time': 1584023446}, {'type': 'Plain', 'text': '@[如果有人看见我在水群请提醒我用功毒树]xzm'}, {'type': 'Plain', 'text': ' 打'}, {'type': 'Plain', 'text': '[图片]'}, {'type': 'Plain', 'text': '吗'}]}, {'type': 'At', 'target': 1924257498, 'display': '@幼天使珈百璃٩(ˊ〇ˋ*)و'}, {'type': 'Plain', 'text': ' 我在打lol'}], 'sender': {'id': 1139329474, 'memberName': '[如果有人看见我在水群请提醒我用功毒树]xzm', 'permission': 'MEMBER', 'group': {'id': 819397581, 'name': '��白菜服开盒中', 'permission': 'MEMBER'}}}

if __name__ == "__main__":
    app.run()