from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.users import User
from app.services.sync import sync_channel

scheduler = AsyncIOScheduler()


async def _sync_all_users() -> None:
    """run a full sync for every user in the db.
    each user gets their own db session so one failure doesn't block the rest."""
    print("auto-sync: starting scheduled sync for all users")

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User))
        users = result.scalars().all()

    print(f"auto-sync: found {len(users)} user(s) to sync")

    for user in users:
        try:
            async with AsyncSessionLocal() as db:
                await sync_channel(db, user)
            print(f"auto-sync: synced user {user.email}")
        except Exception as exc:
            print(f"auto-sync: failed for user {user.email}: {exc}")

    print("auto-sync: done")


def start_scheduler() -> None:
    """register the sync job and start the scheduler.
    runs every 6 hours — first run happens 6 hours after startup, not immediately."""
    scheduler.add_job(
        _sync_all_users,
        trigger="interval",
        hours=6,
        id="sync_all_users",
        replace_existing=True,
    )
    scheduler.start()
    print("auto-sync: scheduler started — will sync every 6 hours")


def stop_scheduler() -> None:
    """gracefully shut down the scheduler on app exit."""
    scheduler.shutdown(wait=False)
    print("auto-sync: scheduler stopped")
