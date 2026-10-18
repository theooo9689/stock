"""Build a public source ZIP, or an explicitly requested PRIVATE configured ZIP."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import sqlite3
import subprocess
import tempfile
import zipfile


def build(output, configured=False):
    root = Path(__file__).resolve().parents[1]
    output = Path(output).resolve()
    if configured and not (root / '.env').is_file():
        raise SystemExit('Configuracao local ausente; nenhum pacote privado foi criado.')
    names = subprocess.check_output(['git', 'ls-files', '-z'], cwd=root).decode().split('\0')
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name in filter(None, names):
            path = root / name
            if not path.is_file():
                continue
            content = path.read_bytes()
            if path.suffix.lower() in ('.cmd', '.ps1'):
                content = content.replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')
            archive.writestr('Radar-Investimentos/' + name, content)
        if configured:
            archive.write(root / '.env', 'Radar-Investimentos/.env')
            database = root / 'data/radar.sqlite3'
            if database.is_file():
                with tempfile.TemporaryDirectory(prefix='radar-backup-') as temp:
                    backup = Path(temp) / 'radar.sqlite3'
                    with sqlite3.connect(database.as_uri() + '?mode=ro', uri=True) as source:
                        with sqlite3.connect(backup) as target:
                            source.backup(target)
                    archive.write(backup, 'Radar-Investimentos/data/radar.sqlite3')
    os.chmod(output, 0o600)
    print('Pacote PRIVADO configurado criado.' if configured else 'Pacote publico sem credenciais criado.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output')
    parser.add_argument('--configured', action='store_true', help='Inclui .env e backup do banco; nao publicar nem compartilhar')
    args = parser.parse_args()
    build(args.output, args.configured)
