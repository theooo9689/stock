"""Forward a user-downloaded official PDF export; never reads a ChatGPT session."""
from __future__ import annotations

import hashlib
from pathlib import Path

from .telegram import Telegram


def forward_pdf(settings, store, path, summary=None, telegram=None):
    path=Path(path)
    if path.suffix.lower()!='.pdf' or not path.is_file() or path.stat().st_size>50_000_000:
        raise ValueError('Selecione um PDF local de até 50 MB exportado manualmente.')
    content=path.read_bytes()
    if not content.startswith(b'%PDF-'):
        raise ValueError('Arquivo não é um PDF válido.')
    text=Path(summary).read_text(encoding='utf-8') if summary else ''
    if len(text)>2000:raise ValueError('O resumo manual deve ter até 2000 caracteres; o PDF segue integral.')
    identifier=hashlib.sha256(content).hexdigest()
    day=settings.now().date().isoformat()
    sender=telegram or Telegram(settings,store)
    # A document stays deduplicated even when its filename or summary changes.
    if text:sender.text(day,'manual-export-summary-'+identifier+'-'+hashlib.sha256(text.encode()).hexdigest()[:12],text)
    sent=sender.send_once(day,'manual-export-pdf-'+identifier,path=path,caption='Relatório exportado manualmente do ChatGPT • arquivo integral, sem reanálise automática.')
    return {'sent':bool(sent),'sha256':identifier,'mode':'manual-official-export','chatgpt_session_access':False}
