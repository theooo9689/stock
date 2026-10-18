from __future__ import annotations

import logging
from datetime import timedelta
from zoneinfo import ZoneInfo

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.triggers.cron import CronTrigger

from .pipeline import run


def start(settings):
    hour, minute = map(int, settings.delivery_time.split(":"))
    prepare = settings.now().replace(hour=hour, minute=minute) - timedelta(hours=1)
    # One executor serializes preparation and delivery if research is still running.
    scheduler = BlockingScheduler(timezone=ZoneInfo(settings.timezone), executors={"default": ThreadPoolExecutor(1)})
    scheduler.add_job(lambda: run(settings, send=False), CronTrigger(hour=prepare.hour, minute=prepare.minute, timezone=settings.timezone),
                      id="pesquisar", coalesce=True, max_instances=1, misfire_grace_time=7200)
    scheduler.add_job(lambda: run(settings, send=True), CronTrigger(hour=hour, minute=minute, timezone=settings.timezone),
                      id="entregar", coalesce=True, max_instances=1, misfire_grace_time=7200)
    logging.getLogger("radar").info("Agendador ativo: pesquisa %02d:%02d, envio %s (%s)", prepare.hour, prepare.minute, settings.delivery_time, settings.timezone)
    scheduler.start()
