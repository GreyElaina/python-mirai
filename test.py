import asyncio
from mirai import Session, Plain, Friend, BotMuteEvent, BotUnmuteEvent, Group, Member, MessageChain, Image, Depend
from devtools import debug
from mirai.misc import printer

authKey = "213we355gdfbaerg"
qq = 208924405

async def main():
    async with Session(f"mirai://localhost:8070/?authKey={authKey}&qq={qq}") as session:
        print(await session.getConfig())

try:
    asyncio.run(main())
except KeyboardInterrupt:
    exit()