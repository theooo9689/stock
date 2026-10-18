"""Hidden Windows worker: Task Scheduler tick or Startup-folder fallback."""
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import sys
import time


def main():
    root = Path(__file__).resolve().parents[2]
    os.chdir(root)
    logs = root / "data" / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s",
                        handlers=[RotatingFileHandler(logs / "radar.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8")])
    # pythonw has no console streams. Discard incidental third-party prints.
    sys.stdout = open(os.devnull, "w")
    sys.stderr = open(os.devnull, "w")
    for name in ("httpx", "httpcore", "openai", "yfinance", "curl_cffi"):
        logging.getLogger(name).setLevel(logging.CRITICAL)
    from radar.config import Settings
    from radar.scheduler import tick
    from radar.storage import Store
    from radar.telegram import Telegram

    def once():
        settings = None
        try:
            settings = Settings.from_env()
            result = tick(settings)
            if result not in ("aguardando_horario", "pesquisa_pronta", "ja_entregue"):
                logging.getLogger("radar").info("Verificacao do agendador: %s", result)
            return 0
        except Exception as exc:
            logging.getLogger("radar").error("Falha na automacao local (%s); nenhum segredo foi registrado", type(exc).__name__)
            if settings:
                try:
                    Telegram(settings, Store(settings.data_dir / "radar.sqlite3")).alert(
                        settings.now().date().isoformat(), f"Falha no radar do notebook ({type(exc).__name__}). Consultar o log local; a tarefa tentara novamente.")
                except Exception:
                    logging.getLogger("radar").error("Alerta Telegram indisponivel")
            return 1

    if "--resident" not in sys.argv:
        return once()
    import portalocker
    lock = portalocker.Lock(str(root / "data" / "worker.lock"), timeout=0)
    try:
        lock.acquire()
    except portalocker.exceptions.LockException:
        return 0
    try:
        while True:
            once()
            time.sleep(30)
    finally:
        lock.release()


if __name__ == "__main__":
    raise SystemExit(main())
