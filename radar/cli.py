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
    r.add_argument('--edition',default='manual',help='Identificador de edição, para prévia/teste sem repetir a edição diária')
    demonstration=sub.add_parser("demo", help="Simulação offline com dados sintéticos; nunca envia")
    demonstration.add_argument("--deep",action="store_true",help="Inclui tese fictícia para demonstrar o layout completo")
    sub.add_parser("preview", help="Renderiza o relatório salvo mais recente do dia; sem rede")
    sub.add_parser("test-telegram", help="Envia mensagem de teste usando destino configurado")
    sub.add_parser("status", help="Mostra custos e estado das entregas; não mostra credenciais")
    sub.add_parser("schedule", help="Processo residente para servidor ligado continuamente")
    sub.add_parser("tick", help="Verifica o horário de Brasília e retoma a edição do dia após ligar o notebook")
    sub.add_parser('doctor',help='Checa Ollama/modelo e informa hardware sem usar API paga')
    replay=sub.add_parser('replay',help='Reprocessa arquivo histórico com a metodologia atual, sem pesquisa/negociação')
    replay.add_argument('input',type=Path)
    versions=sub.add_parser('versions',help='Lista versões imutáveis do dia')
    versions.add_argument('--day')
    frozen=sub.add_parser('render-version',help='Renderiza resposta congelada de uma versão; sem inferência/rede')
    frozen.add_argument('id')
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
            report, paths = run(settings, send=args.send, ai=not args.no_ai, refresh=args.refresh,edition=args.edition)
            print(json.dumps({"status": report["status"], "assets": len(report["assets"]), "paths": {k: str(v) for k,v in paths.items()}}, ensure_ascii=False))
        elif args.command in ("demo", "preview"):
            from .demo import demo_report, premium_sample_report
            from .report import generate
            report = (premium_sample_report(settings) if args.deep else demo_report(settings)) if args.command == "demo" else store.report(day)
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
        elif args.command == "tick":
            from .scheduler import tick
            print(tick(settings))
        elif args.command == 'versions':
            print(json.dumps(store.versions(args.day or day)))
        elif args.command == 'render-version':
            from .report import generate
            report=store.report_version(args.id)
            if report is None:raise RuntimeError('Versão não encontrada')
            print(json.dumps({k:str(v) for k,v in generate(report,settings.reports_dir).items()},ensure_ascii=False))
        elif args.command == 'doctor':
            from .local_ai import Ollama,LocalAIError
            import psutil
            ram=round(psutil.virtual_memory().total/2**30,1)
            result={'ram_gb':ram,'recommended_model':'qwen3:14b' if ram>=32 else 'qwen3:8b' if ram>=16 else 'Modelo ≥7B exige mais RAM/contexto; não usar modelo pequeno para mascarar incapacidade.'}
            try:result.update(Ollama(settings,store).doctor())
            except LocalAIError as exc:result.update(ready=False,reason=str(exc))
            print(json.dumps(result,ensure_ascii=False))
        elif args.command == 'replay':
            from .premium import upgrade_report
            from .report import generate
            from .config import Watchlist
            report=upgrade_report(json.loads(args.input.read_text(encoding='utf-8')),Watchlist.load(settings.config_path))
            paths=generate(report,settings.reports_dir)
            print(json.dumps({k:str(v) for k,v in paths.items()},ensure_ascii=False))
    except Exception as exc:
        # Exception messages from SDKs may contain tokens or private destination IDs.
        logging.getLogger("radar").error("Operação interrompida (%s); detalhes privados não registrados", type(exc).__name__)
        if args.command in ("run", "schedule", "tick"):
            try:
                from .telegram import Telegram
                Telegram(settings, store).alert(day, f"Execução interrompida ({type(exc).__name__}). O relatório não foi concluído/enviado integralmente. Verificar o ambiente do agendador.")
            except Exception:
                logging.getLogger("radar").error("Alerta Telegram também indisponível")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
