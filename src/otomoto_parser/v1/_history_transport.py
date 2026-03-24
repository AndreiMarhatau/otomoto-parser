from __future__ import annotations

from http.cookiejar import CookieJar
from urllib.request import HTTPCookieProcessor, build_opener

from ._history_common import INIT_URL, OpenerLike


def _discover_cookie_jar(opener: OpenerLike | None, cookie_jar: CookieJar | None) -> CookieJar:
    if cookie_jar is not None:
        return cookie_jar
    for handler in getattr(opener, "handlers", []):
        if isinstance(handler, HTTPCookieProcessor):
            return handler.cookiejar
    return CookieJar()


def _build_opener_with_cookies(opener: OpenerLike | None, cookie_jar: CookieJar):
    if opener is None:
        return build_opener(HTTPCookieProcessor(cookie_jar))
    for handler in getattr(opener, "handlers", []):
        if isinstance(handler, HTTPCookieProcessor):
            handler.cookiejar = cookie_jar
            return opener
    if hasattr(opener, "add_handler"):
        opener.add_handler(HTTPCookieProcessor(cookie_jar))
    return opener


def _bootstrap_headers(accept_language: str, user_agent: str) -> dict[str, str]:
    return {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": accept_language,
        "Content-Type": "application/x-www-form-urlencoded",
        "Origin": "null",
        "Referer": INIT_URL,
        "User-Agent": user_agent,
    }


def _data_headers(accept_language: str, user_agent: str, nf_wid: str, xsrf_token: str) -> dict[str, str]:
    return {
        "Accept": "application/json",
        "Accept-Language": accept_language,
        "Content-Type": "application/json",
        "NF_WID": nf_wid,
        "Origin": "https://moj.gov.pl",
        "User-Agent": user_agent,
        "X-XSRF-TOKEN": xsrf_token,
    }
