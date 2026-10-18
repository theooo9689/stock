from __future__ import annotations

import logging
from datetime import timedelta
from zoneinfo import ZoneInfo

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.triggers.cron import CronTrigger

from .pipeline import run, RunInProgress
from .storage import Store


def tick(settings, runner=None):
    """One cheap check, suitable for Windows Task Scheduler and resume from sleep."""
    runner = runner or run
    now = settings.now()
    day = now.date().isoformat()
    hour, minute = map(int, settings.delivery_time.split(":"))
    due = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    prepare = due - timedelta(hours=1)
    if now < prepare:
        return "aguardando_horario"
    store = Store(settings.data_dir / "radar.sqlite3")
    states = store.delivery_states(day)
    if states.get("scheduled-concluido") == "sent":
        return "ja_entregue"
    if any(k.startswith("scheduled-") and v == "sending" for k, v in states.items()):
        logging.getLogger("radar").warning("Entrega incerta: verificar o Telegram antes de liberar reenvio")
        return "entrega_incerta"
    report = store.report(day)
    prepared = False
    if report:
        try:
            from datetime import datetime
            generated = datetime.fromisoformat(report["generated_at"])
            prepared = generated.tzinfo is not None and generated >= prepare
        except (KeyError, ValueError):
            pass
    try:
        if now < due:
            if prepared:
                return "pesquisa_pronta"
            runner(settings, send=False, refresh=True, edition="scheduled")
            return "pesquisado"
        runner(settings, send=True, refresh=bool(report and not prepared), edition="scheduled")
        return "entrega_processada"
    except RunInProgress:
        return "em_execucao"


def start(settings):
    hour, minute = map(int, settings.delivery_time.split(":"))
    prepare = settings.now().replace(hour=hour, minute=minute) - timedelta(hours=1)
    # One executor serializes preparation and delivery if research is still running.
    scheduler = BlockingScheduler(timezone=ZoneInfo(settings.timezone), executors={"default": ThreadPoolExecutor(1)})
    scheduler.add_job(lambda: run(settings, send=False, refresh=True), CronTrigger(hour=prepare.hour, minute=prepare.minute, timezone=settings.timezone),
                      id="pesquisar", coalesce=True, max_instances=1, misfire_grace_time=7200)
    scheduler.add_job(lambda: run(settings, send=True, edition="scheduled"), CronTrigger(hour=hour, minute=minute, timezone=settings.timezone),
                      id="entregar", coalesce=True, max_instances=1, misfire_grace_time=7200)
    logging.getLogger("radar").info("Agendador ativo: pesquisa %02d:%02d, envio %s (%s)", prepare.hour, prepare.minute, settings.delivery_time, settings.timezone)
    scheduler.start()
