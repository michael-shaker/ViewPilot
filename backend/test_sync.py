"""quick test script to trigger a channel sync directly, bypassing http/auth."""
import asyncio
from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.models.users import User
from app.services.sync import sync_channel


async def main():
    async with AsyncSessionLocal() as db:
        # grab the first user in the database
        result = await db.execute(select(User).limit(1))
        user = result.scalar_one_or_none()
        if not user:
            print("no users found — log in first via the oauth flow")
            return

        print(f"syncing channel for {user.email}...")
        channel = await sync_channel(db, user)
        print(f"done! channel: {channel.title}")
        print(f"videos synced: {channel.video_count}")


asyncio.run(main())
