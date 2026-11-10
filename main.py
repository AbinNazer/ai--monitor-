import asyncio
from db.session import init_db
from poller.scheduler import run_forever
from bot.client import start_bot


async def main():
    await init_db()
    await asyncio.gather(
        run_forever(),
        start_bot(),
    )


if __name__ == "__main__":
    asyncio.run(main())