import asyncio

async def t1():
    raise TypeError("?")

async def main():
    asyncio.create_task(t1())
    print("??")

asyncio.run(main())