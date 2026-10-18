"""Enviar secrets locais ao GitHub via stdin, sem exibir credenciais."""
import subprocess
import sys

from dotenv import dotenv_values

if len(sys.argv) != 2:
    raise SystemExit("Uso: python scripts/configure_github_secrets.py OWNER/REPO")
values = dotenv_values('.env')
for name in ('TELEGRAM_BOT_TOKEN', 'TELEGRAM_CHAT_ID', 'OPENAI_API_KEY'):
    value = values.get(name)
    if not value:
        raise SystemExit(f"Secret ausente no ambiente local: {name}")
    result = subprocess.run(['gh','secret','set',name,'--repo',sys.argv[1]], input=value.encode(), capture_output=True)
    if result.returncode:
        raise SystemExit(f"GitHub recusou configurar {name}. Verificar permissão de Actions secrets; nenhum valor foi impresso.")
    print(f"Configurado: {name}")
