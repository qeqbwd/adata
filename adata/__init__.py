# -*- coding: utf-8 -*-
"""
@desc: adata
@author: upstream adata
"""

import logging

from adata.__version__ import __version__
from adata.bond import bond
from adata.fund import fund
from adata.sentiment import sentiment
from adata.stock import stock
from adata.common.utils.sunrequests import SunProxy, SunRequests


def version():
    return __version__


def proxy(is_proxy: bool = False, ip: str = None, proxy_url: str = None):
    """
    设置请求代理
    :param is_proxy: 是否启用代理，默认：否
    :param ip: 代理ip地址；格式样例：192.123.123.4:4568
    :param proxy_url: 能获取到代理的url，返回格式必须和ip一样（本次为最小改动不强制实现拉取）
    """
    SunProxy.set("is_proxy", is_proxy)
    SunProxy.set("ip", ip)
    SunProxy.set("proxy_url", proxy_url)
    return


def set_rate_limit(per_minute: int = 30):
    """
    设置全局默认：同一域名每分钟最多请求次数
    - 默认 30 次/分钟
    - 设为 0 表示关闭限流
    """
    SunRequests.set_rate_limit(per_minute)


# set up logging
logger = logging.getLogger("adata")


def set_logger():
    format_string = "%(asctime)s - %(levelname)s - %(message)s"
    formatter = logging.Formatter(format_string, datefmt="%Y-%m-%dT%H:%M:%S")
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    logger.addHandler(handler)


set_logger()
