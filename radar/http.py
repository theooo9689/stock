from __future__ import annotations

import ipaddress
import logging
import time
from urllib.parse import urlparse, urljoin

import httpx

USER_AGENT = "RadarInvestimentos/1.0 (https://github.com/theooo9689/stock)"


def safe_url(url):
    try:
        p = urlparse(url)
        if p.scheme != "https" or not p.hostname or p.username or p.password or p.port not in (None, 443):
            return False
        host = p.hostname.lower()
        if host == "localhost" or host.endswith((".local", ".internal")) or "." not in host:
            return False
        try:
            return ipaddress.ip_address(host).is_global
        except ValueError:
            return True
    except ValueError:
        return False


class APIError(RuntimeError):
    pass


class HTTP:
    def __init__(self, store, client=None):
        self.store = store
        self.client = client or httpx.Client(timeout=30, headers={"User-Agent": USER_AGENT}, follow_redirects=False)
        # HTTP debug logs include Telegram paths and provider query-string secrets.
        for name in ("httpx", "httpcore", "openai", "yfinance", "curl_cffi"):
            logging.getLogger(name).setLevel(logging.CRITICAL)

    def get(self, url, params=None, *, ttl=3600, cache_key=None, json_response=True):
        if not safe_url(url):
            raise APIError("URL de fonte inválida")
        key = cache_key or str(httpx.URL(url, params=params))
        cached = self.store.cached(key)
        if cached is not None:
            return cached
        for attempt in range(3):
            try:
                target, query = url, params
                for redirect in range(4):
                    r = self.client.get(target, params=query)
                    if r.status_code not in (301,302,303,307,308):break
                    destination=urljoin(str(r.url),r.headers.get('Location',''))
                    if not safe_url(destination) or redirect==3:raise APIError('Redirecionamento de fonte recusado')
                    target,query=destination,None
            except httpx.TransportError:
                if attempt == 2:
                    raise APIError("Falha de transporte no provedor") from None
                time.sleep(2 ** attempt)
                continue
            if r.status_code == 429 or r.status_code >= 500:
                if attempt < 2:
                    try:
                        delay = min(10, max(0, float(r.headers.get("Retry-After", 2 ** attempt))))
                    except ValueError:
                        delay = 2 ** attempt
                    time.sleep(delay)
                    continue
            if r.status_code >= 300:
                raise APIError(f"Provedor retornou HTTP {r.status_code}")
            try:
                result = r.json() if json_response else r.text
            except ValueError:
                raise APIError("Resposta inválida do provedor") from None
            self.store.cache(key, result, ttl)
            return result
        raise APIError("Tentativas esgotadas")
