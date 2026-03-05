# -*- coding: utf-8 -*-
"""
@desc: requests wrapper with retry/proxy + per-domain rate limit
@author: upstream adata
"""

import time
import threading
from collections import deque
from urllib.parse import urlparse

import requests


class SunProxy:
    """
    原项目的代理配置容器（保持接口不变）
    """
    _conf = {
        "is_proxy": False,
        "ip": None,
        "proxy_url": None
    }

    @classmethod
    def set(cls, k, v):
        cls._conf[k] = v

    @classmethod
    def get(cls, k, default=None):
        return cls._conf.get(k, default)


class RateLimiter:
    """
    基于域名的滑动窗口限流器：
    - 同一 domain 在 window_seconds 内最多 limit 次
    - 默认 30 次/分钟（可全局设置，也可每次 request 传参覆盖）
    """
    def __init__(self, default_limit_per_minute: int = 30, window_seconds: int = 60):
        self._default = int(default_limit_per_minute or 0)
        self._window = int(window_seconds)
        self._lock = threading.Lock()
        self._buckets = {}  # domain -> deque[timestamps]

    def set_default(self, limit_per_minute: int):
        self._default = int(limit_per_minute or 0)

    def default(self) -> int:
        return self._default

    def acquire(self, domain: str, limit_per_minute: int | None = None):
        """
        阻塞直到允许请求（如果 limit=0 则不限制）
        """
        limit = self._default if limit_per_minute is None else int(limit_per_minute or 0)
        if limit <= 0:
            return

        if not domain:
            # 无法解析域名就不做限制（尽量不破坏兼容性）
            return

        # 取 bucket（每个域名一个 deque）
        with self._lock:
            dq = self._buckets.get(domain)
            if dq is None:
                dq = deque()
                self._buckets[domain] = dq

        # 滑动窗口控制
        while True:
            now = time.time()
            with self._lock:
                # 清理过期
                expire_before = now - self._window
                while dq and dq[0] <= expire_before:
                    dq.popleft()

                if len(dq) < limit:
                    dq.append(now)
                    return

                # 需要等待到最早一次请求过期
                wait_for = (dq[0] + self._window) - now
                if wait_for < 0:
                    wait_for = 0.0

            # 锁外 sleep，避免阻塞其他域名
            time.sleep(wait_for if wait_for > 0 else 0.001)


class SunRequests:
    """
    统一请求封装
    """
    _rate_limiter = RateLimiter(default_limit_per_minute=30)

    @classmethod
    def set_rate_limit(cls, per_minute: int):
        """
        设置全局默认：同一域名每分钟最多请求次数
        per_minute=0 表示关闭限流
        """
        cls._rate_limiter.set_default(per_minute)

    @staticmethod
    def _extract_domain(url: str) -> str:
        try:
            parsed = urlparse(url)
            return parsed.netloc or ""
        except Exception:
            return ""

    @staticmethod
    def _proxy_dict():
        """
        按原项目约定返回 proxies dict
        """
        if not SunProxy.get("is_proxy", False):
            return None

        ip = SunProxy.get("ip")
        proxy_url = SunProxy.get("proxy_url")

        # 若提供 proxy_url，可在此扩展成“从 URL 拉取代理”的逻辑
        # 但为最小改动，这里保持与原项目一致：优先使用 ip
        if not ip and proxy_url:
            # 这里不强行实现下载代理，避免引入额外依赖/不确定行为
            pass

        if not ip:
            return None

        return {
            "http": f"http://{ip}",
            "https": f"http://{ip}",
        }

    @classmethod
    def request(
        cls,
        method: str,
        url: str,
        retry: int = 3,
        wait: float = 0.2,
        rate_limit: int | None = None,
        **kwargs
    ):
        """
        :param rate_limit: 覆盖全局默认（同一域名每分钟请求次数）
                           - None：使用全局默认（默认 30）
                           - 0：本次禁用限流
                           - N：本次按 N 次/分钟限流
        """
        # 1) 频率限制（同域名）
        domain = cls._extract_domain(url)
        cls._rate_limiter.acquire(domain, rate_limit)

        # 2) 代理
        proxies = cls._proxy_dict()
        if proxies and "proxies" not in kwargs:
            kwargs["proxies"] = proxies

        # 3) 重试
        last_err = None
        for i in range(max(1, int(retry))):
            try:
                resp = requests.request(method=method, url=url, **kwargs)
                return resp
            except Exception as e:
                last_err = e
                if i < retry - 1:
                    time.sleep(wait)
        raise last_err


# 与原项目 usage 兼容：其他模块一般 `from adata.common.utils import requests`
sun_requests = SunRequests
