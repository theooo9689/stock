from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from .config import Settings
from .storage import Store


def main():
    p = argparse.ArgumentParser(description="Radar diário de investimentos — não executa ordens")
    sub = p.add_subparsers(dest="command", required=True)
    r = sub.add_parser("run", help="Coleta, pesquisa e gera relatório; usa resultado salvo do dia")
    r.add_argument("--send", action="store_true")
    r.add_argument("--no-ai", action="store_true")
    r.add_argument("--refresh", action="store_true", help="Refazer pesquisa respeitando orçamento, sem reenviar partes já entregues")
    sub.add_parser("demo", help="Simulação offline com dados sintéticos; nunca envia")
    sub.add_parser("preview", help="Renderiza o relatório salvo mais recente do dia; sem rede")
    sub.add_parser("test-telegram", help="Envia mensagem de teste usando destino configurado")
    sub.add_parser("status", help="Mostra custos e estado das entregas; não mostra credenciais")
    sub.add_parser("schedule", help="Processo residente para servidor ligado continuamente")
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    # Prevent provider request URLs from entering logs.
    for name in ("httpx", "httpcore", "openai", "yfinance", "curl_cffi"):
        logging.getLogger(name).setLevel(logging.CRITICAL)
    settings = Settings.from_env()
    store = Store(settings.data_dir / "radar.sqlite3")
    day = settings.now().date().isoformat()
    try:
        if args.command == "run":
            from .pipeline import run
            report, paths = run(settings, send=args.send, ai=not args.no_ai, refresh=args.refresh)
            print(json.dumps({"status": report["status"], "assets": len(report["assets"]), "paths": {k: str(v) for k,v in paths.items()}}, ensure_ascii=False))
        elif args.command in ("demo", "preview"):
            from .demo import demo_report
            from .report import generate
            report = demo_report(settings) if args.command == "demo" else store.report(day)
            if report is None:
                raise RuntimeError("Nenhum relatório salvo para hoje")
            paths = generate(report, settings.reports_dir)
            print(json.dumps({k: str(v) for k,v in paths.items()}))
        elif args.command == "test-telegram":
            from .telegram import Telegram
            Telegram(settings, store).text(day, "teste-conexao", "Radar de Investimentos: conexão confirmada. Entrega prevista para 20h30 de Brasília quando o agendador estiver ativo.")
            print("Teste processado; envios repetidos no mesmo dia são ignorados.")
        elif args.command == "status":
            spent, reserved = store.cost(day)
            print(json.dumps({"day": day, "estimated_usd": spent, "reserved_usd": reserved, "deliveries": store.delivery_states(day)}, ensure_ascii=False))
        elif args.command == "schedule":
            from .scheduler import start
            start(settings)
    except Exception as exc:
        # Exception messages from SDKs may contain tokens or private destination IDs.
        logging.getLogger("radar").error("Operação interrompida (%s); detalhes privados não registrados", type(exc).__name__)
        if args.command in ("run", "schedule"):
            try:
                from .telegram import Telegram
                Telegram(settings, store).alert(day, f"Execução interrompida ({type(exc).__name__}). O relatório não foi concluído/enviado integralmente. Verificar o ambiente do agendador.")
            except Exception:
                logging.getLogger("radar").error("Alerta Telegram também indisponível")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
