"""Polite, cached HTTP fetching.

Design goals (per the task rules):
  * Respect robots.txt for every domain.
  * Throttle to at most 1 request / ``PER_DOMAIN_DELAY`` seconds per domain.
  * Cache every fetched page on disk so reruns are incremental.
  * Trust the agent-proxy CA bundle if present (env REQUESTS_CA_BUNDLE is also
    honoured by requests automatically; we set it explicitly as a fallback).

Nothing here fabricates data — it only fetches and stores what a server returns.
"""

from __future__ import annotations

import hashlib
import os
import time
import urllib.robotparser
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import requests

USER_AGENT = (
    "LuckySingsBookingResearch/1.0 (+contact research; polite crawler; "
    "1 req/2s per domain)"
)
PER_DOMAIN_DELAY = 2.0          # seconds between requests to the same host
REQUEST_TIMEOUT = 25           # seconds
CA_BUNDLE = "/root/.ccr/ca-bundle.crt"


def _default_cache_dir() -> Path:
    return Path(os.environ.get("CZ_CACHE_DIR", ".cache/pages"))


@dataclass
class FetchResult:
    url: str
    status: int
    text: str
    from_cache: bool
    final_url: str = ""
    blocked_by_robots: bool = False


class Fetcher:
    def __init__(self, cache_dir: Optional[Path] = None, delay: float = PER_DOMAIN_DELAY):
        self.cache_dir = Path(cache_dir) if cache_dir else _default_cache_dir()
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.delay = delay
        self._last_hit: dict[str, float] = {}
        self._robots: dict[str, Optional[urllib.robotparser.RobotFileParser]] = {}
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})
        if os.path.exists(CA_BUNDLE):
            self.session.verify = CA_BUNDLE

    # -- cache -------------------------------------------------------------
    def _cache_path(self, url: str) -> Path:
        h = hashlib.sha256(url.encode("utf-8")).hexdigest()[:24]
        host = (urlparse(url).hostname or "nohost").replace(":", "_")
        sub = self.cache_dir / host
        sub.mkdir(parents=True, exist_ok=True)
        return sub / f"{h}.html"

    def _read_cache(self, url: str) -> Optional[str]:
        p = self._cache_path(url)
        if p.exists():
            try:
                return p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                return None
        return None

    def _write_cache(self, url: str, text: str) -> None:
        try:
            self._cache_path(url).write_text(text, encoding="utf-8", errors="replace")
        except OSError:
            pass

    # -- robots ------------------------------------------------------------
    def _robots_for(self, url: str) -> Optional[urllib.robotparser.RobotFileParser]:
        parsed = urlparse(url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        if base in self._robots:
            return self._robots[base]
        rp = urllib.robotparser.RobotFileParser()
        robots_url = base + "/robots.txt"
        try:
            self._throttle(parsed.hostname or base)
            resp = self.session.get(robots_url, timeout=REQUEST_TIMEOUT)
            if resp.status_code >= 400:
                rp = None  # no robots => allowed
            else:
                rp.parse(resp.text.splitlines())
        except requests.RequestException:
            rp = None
        self._robots[base] = rp
        return rp

    def allowed(self, url: str) -> bool:
        rp = self._robots_for(url)
        if rp is None:
            return True
        return rp.can_fetch(USER_AGENT, url)

    # -- throttle ----------------------------------------------------------
    def _throttle(self, host: str) -> None:
        now = time.monotonic()
        last = self._last_hit.get(host)
        if last is not None:
            wait = self.delay - (now - last)
            if wait > 0:
                time.sleep(wait)
        self._last_hit[host] = time.monotonic()

    # -- fetch -------------------------------------------------------------
    def get(self, url: str, use_cache: bool = True) -> FetchResult:
        if use_cache:
            cached = self._read_cache(url)
            if cached is not None:
                return FetchResult(url, 200, cached, from_cache=True, final_url=url)

        if not self.allowed(url):
            return FetchResult(url, 0, "", from_cache=False, blocked_by_robots=True)

        host = urlparse(url).hostname or url
        self._throttle(host)
        try:
            resp = self.session.get(url, timeout=REQUEST_TIMEOUT, allow_redirects=True)
        except requests.RequestException as exc:  # network / TLS / timeout
            return FetchResult(url, -1, f"__ERROR__ {exc}", from_cache=False)

        text = resp.text if resp.status_code == 200 else ""
        if resp.status_code == 200:
            self._write_cache(url, text)
        return FetchResult(
            url, resp.status_code, text, from_cache=False, final_url=str(resp.url)
        )
