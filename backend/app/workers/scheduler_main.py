"""Scheduled jobs (APScheduler).

  08:00 IST  -> instrument master sync
  15:15 IST  -> MIS auto square-off (equity/derivatives intraday)
  15:45 IST  -> EOD: square-off sweep + T+1 holdings settlement
"""
from __future__ import annotations

import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.calendar import IST, is_holiday, now_ist
from app.db import SessionLocal
from app.models.enums import Segment
from app.services import instrument_service, settlement

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("scheduler")


def _trading_day() -> bool:
    return not is_holiday(now_ist().date(), Segment.EQ)


async def job_sync_instruments() -> None:
    async with SessionLocal() as db:
        try:
            n = await instrument_service.sync_instrument_master(db)
            await db.commit()
            logger.info("instrument master sync: %d rows", n)
        except Exception as exc:  # noqa: BLE001
            logger.error("instrument sync failed: %s", exc)


async def job_square_off_mis() -> None:
    if not _trading_day():
        return
    async with SessionLocal() as db:
        n = await settlement.square_off_mis(db)
        await db.commit()
        logger.info("15:15 MIS square-off: %d position(s)", n)


async def job_eod() -> None:
    if not _trading_day():
        return
    async with SessionLocal() as db:
        result = await settlement.run_eod(db)
        await db.commit()
        logger.info("EOD: %s", result)


def build_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=IST)
    scheduler.add_job(job_sync_instruments, CronTrigger(hour=8, minute=0), id="sync_instruments")
    scheduler.add_job(job_square_off_mis, CronTrigger(hour=15, minute=15), id="square_off_mis")
    scheduler.add_job(job_eod, CronTrigger(hour=15, minute=45), id="eod")
    return scheduler


async def _boot_sync() -> None:
    """Fill / refresh the instrument table on boot instead of waiting for 08:00.

    Fully defensive: any DB/schema hiccup here must not stop the scheduler — the
    08:00 cron job is still registered and the API's /instruments/sync endpoint
    is available as a fallback.
    """
    from sqlalchemy import func, select

    from app.models import Instrument
    from app.models.enums import AssetCategory

    try:
        async with SessionLocal() as db:
            total = (await db.execute(select(func.count(Instrument.id)))).scalar_one()
            try:
                classified = (
                    await db.execute(
                        select(func.count(Instrument.id)).where(
                            Instrument.category != AssetCategory.OTHER.value
                        )
                    )
                ).scalar_one()
            except Exception:  # noqa: BLE001 - column may not exist yet
                classified = 0
        needs = total == 0 or classified == 0
        logger.info("boot instrument check: rows=%d classified=%d needs_sync=%s",
                    total, classified, needs)
        if needs:
            await job_sync_instruments()
    except Exception as exc:  # noqa: BLE001
        logger.warning("boot instrument sync skipped: %s", exc)


async def run() -> None:
    scheduler = build_scheduler()
    scheduler.start()
    logger.info("scheduler started: %s", [j.id for j in scheduler.get_jobs()])

    await _boot_sync()

    try:
        while True:
            await asyncio.sleep(3600)
    finally:
        scheduler.shutdown(wait=False)


if __name__ == "__main__":
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        pass
