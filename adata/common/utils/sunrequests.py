# -*- coding: utf-8 -*-
import time
import threading
from collections import deque
from urllib.parse import urlparse

import requests


class _DomainRateLimiter:
    """
    Per-domain sliding window limiter.
    Default: 30 req / 60s per domain.
    """

    def __init__(self, default_per_minute: int = 30, window_seconds: int = 60):
        self._default = int(default_per_minute) if default_per_minute is not None else 30
        self._window = int(window_seconds)
        self._lock = threading.Lock()
        # domain -> deque[timestamps]
        self._buckets = {}

    def set_default(self, per_minute: int):
        with self._lock:
            self._default = int(per_minute)

    def _get_domain(self, url: str) -> str:
        try:
            return (urlparse(url).netloc or "").lower()
        except Exception:
            return ""

    def acquire(self, url: str, per_minute: int = None):
        """
        Block until allowed.
        per_minute:
          - None: use global default
          - 0 or <0: disable rate limit for this request
        """
        limit = self._default if per_minute is None else int(per_minute)
        if limit <= 0:
            return

        domain = self._get_domain(url)
        if not domain:
            # no domain => don't block
            return

        while True:
            now = time.time()
            with self._lock:
                q = self._buckets.get(domain)
                if q is None:
                    q = deque()
                    self._buckets[domain] = q

                # clear expired
                expire_before = now - self._window
                while q and q[0] <= expire_before:
                    q.popleft()

                if len(q) < limit:
                    q.append(now)
                    return

                # need wait until oldest expires
                wait_s = (q[0] + self._window) - now
                if wait_s < 0:
                    wait_s = 0.0

            # sleep outside lock
            time.sleep(wait_s + 0.001)


class SunRequests(object):
    """
    requests wrapper used by this project.
    Add per-domain rate limit at unified入口, so call sites don't need changes.
    """

    def __init__(self):
        self._limiter = _DomainRateLimiter(default_per_minute=30, window_seconds=60)

    def set_rate_limit(self, per_minute: int):
        """
        Set global default rate limit per domain per minute.
        per_minute <= 0 => disable globally.
        """
        self._limiter.set_default(per_minute)

    def request(self, method, url, *, rate_limit: int = None, **kwargs):
        """
        rate_limit:
          - None: use global default (30/min/domain)
          - >0  : override for this call
          - <=0 : disable for this call
        """
        self._limiter.acquire(url, rate_limit)
        return requests.request(method=method, url=url, **kwargs)

    def get(self, url, *, rate_limit: int = None, **kwargs):
        return self.request("get", url, rate_limit=rate_limit, **kwargs)

    def post(self, url, *, rate_limit: int = None, **kwargs):
        return self.request("post", url, rate_limit=rate_limit, **kwargs)


# project-style singleton export
sun_requests = SunRequests()
