from __future__ import annotations

import time
import html
from html.parser import HTMLParser
from pathlib import Path

import httpx


def chunks(text, limit=3800):
    # Telegram counts UTF-16 code units; stay below 4096 even with emoji.
    result, current, size = [], [], 0
    for line in text.splitlines(keepends=True):
        for char in line:
            width = len(char.encode("utf-16-le")) // 2
            if size + width > limit:
                result.append("".join(current))
                current, size = [], 0
            current.append(char)
            size += width
    if current:
        result.append("".join(current))
    return result


def html_chunks(text, limit=3800):
    """Split text nodes, never tags/entities; close/reopen formatting at boundaries."""
    class Splitter(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.stack=[];self.current=[];self.parts=[];self.size=0
        def flush(self):
            if self.size:
                self.parts.append(''.join(self.current)+''.join('</'+t+'>' for t,_ in reversed(self.stack)))
            self.current=[opening for _,opening in self.stack];self.size=0
        def handle_starttag(self,tag,attrs):
            if tag not in ('b','strong','i','em','u','s','code','pre','a'):raise ValueError('Tag HTML não suportada')
            opening='<'+tag+''.join(' '+k+'="'+html.escape(v or '',quote=True)+'"' for k,v in attrs if tag=='a' and k=='href')+'>'
            self.current.append(opening);self.stack.append((tag,opening))
        def handle_endtag(self,tag):
            if not self.stack or self.stack[-1][0]!=tag:raise ValueError('HTML desbalanceado')
            self.stack.pop();self.current.append('</'+tag+'>')
        def handle_data(self,data):
            for char in data:
                width=len(char.encode('utf-16-le'))//2
                if self.size+width>limit:self.flush()
                self.current.append(html.escape(char,quote=False));self.size+=width
    parser=Splitter();parser.feed(text);parser.close()
    if parser.stack:raise ValueError('HTML incompleto')
    parser.flush()
    return parser.parts


class TelegramError(RuntimeError):
    def __init__(self, message, ambiguous=False):
        super().__init__(message)
        self.ambiguous = ambiguous


class Telegram:
    def __init__(self, settings, store, client=None):
        self.base = "https://api.telegram.org/bot" + settings.telegram_token.get_secret_value()
        self.chat = settings.telegram_chat.get_secret_value()
        self.store = store
        self.client = client or httpx.Client(timeout=90)
        if not settings.telegram_token.get_secret_value() or not self.chat:
            raise TelegramError("Token ou destino do Telegram não configurado")

    def call(self, method, data, files=None):
        for attempt in range(3):
            try:
                r = self.client.post(self.base + "/" + method, data={"chat_id": self.chat, **data}, files=files)
            except (httpx.ReadTimeout, httpx.WriteTimeout, httpx.RemoteProtocolError):
                raise TelegramError("Resultado de envio incerto; conciliar antes de reenviar", ambiguous=True) from None
            except (httpx.ConnectError, httpx.ConnectTimeout, httpx.PoolTimeout):
                if attempt < 2:
                    time.sleep(2 ** attempt)
                    continue
                raise TelegramError("Não foi possível conectar ao Telegram") from None
            try:
                payload = r.json()
            except ValueError:
                raise TelegramError("Resposta de envio inválida; resultado incerto", ambiguous=True) from None
            if payload.get("ok"):
                return payload["result"]["message_id"]
            if r.status_code == 429 and attempt < 2:
                wait = min(30, payload.get("parameters", {}).get("retry_after", 2 ** attempt))
                time.sleep(wait)
                continue
            # Do not blindly retry 5xx POST requests: Telegram has no idempotency key.
            raise TelegramError(f"Telegram HTTP {r.status_code}", ambiguous=r.status_code >= 500)
        raise TelegramError("Limite de tentativas do Telegram atingido")

    def send_once(self, day, part, text=None, path=None, caption=None, parse_mode=None):
        if not self.store.claim_delivery(day, part):
            return False
        try:
            if path:
                path = Path(path)
                # Bytes allow safe retry after an explicit Telegram 429.
                msg = self.call("sendDocument", {"caption": caption or path.name}, {"document": (path.name, path.read_bytes(), "application/pdf" if path.suffix == ".pdf" else "application/json")})
            else:
                msg = self.call("sendMessage", {"text": text, "link_preview_options": '{"is_disabled":true}', **({'parse_mode':parse_mode} if parse_mode else {})})
            self.store.sent(day, part, msg)
            return True
        except TelegramError as exc:
            if not exc.ambiguous:
                self.store.release_delivery(day, part)
            raise

    def text(self, day, part, text, parse_mode=None):
        sent = 0
        for i, content in enumerate(html_chunks(text) if parse_mode=='HTML' else chunks(text)):
            sent += self.send_once(day, f"{part}-{i+1}", text=content, parse_mode=parse_mode)
        return sent

    def alert(self, day, text):
        return self.text(day, "alerta-operacional", "ALERTA OPERACIONAL — RADAR\n" + text)
