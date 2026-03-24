import http.client
import json
import threading
import time
from http.cookiejar import Cookie, CookieJar
from urllib.request import HTTPCookieProcessor, build_opener
from urllib.error import HTTPError

import pytest

from otomoto_parser.v1.history_report import (
    VehicleHistoryClient,
    build_arg_parser,
    _normalize_first_registration_date,
    _normalize_registration_number,
    _normalize_vin_number,
    _with_retry,
)


def _make_cookie(name: str, value: str) -> Cookie:
    return Cookie(
        version=0,
        name=name,
        value=value,
        port=None,
        port_specified=False,
        domain="moj.gov.pl",
        domain_specified=True,
        domain_initial_dot=False,
        path="/",
        path_specified=True,
        secure=True,
        expires=None,
        discard=True,
        comment=None,
        comment_url=None,
        rest={},
        rfc2109=False,
    )


class _FakeResponse:
    def __init__(self, body: str, status: int = 200) -> None:
        self.body = body.encode("utf-8")
        self.status = status

    def read(self) -> bytes:
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


class _FakeOpener:
    def __init__(self, handler) -> None:
        self.handler = handler
        self.requests = []

    def open(self, request, timeout=0):
        self.requests.append(request)
        return self.handler(request)


def test_normalize_first_registration_date() -> None:
    assert _normalize_first_registration_date("2005-01-01") == "2005-01-01"
    assert _normalize_registration_number("LUB 0835R") == "LUB0835R"
    assert _normalize_vin_number(" wdd sj4eb2 en056917 ") == "WDDSJ4EB2EN056917"


def test_normalize_first_registration_date_rejects_non_iso_input() -> None:
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        _normalize_first_registration_date("01.01.2005")


def test_cli_help_advertises_only_iso_date_format() -> None:
    parser = build_arg_parser()
    help_text = parser.format_help()
    assert "YYYY-MM-DD" in help_text
    assert "DD.MM.YYYY" not in help_text


def test_fetch_report_bootstraps_session_and_reuses_nf_wid() -> None:
    jar = CookieJar()

    def handler(request):
        if "engine/ng/index" in request.full_url:
            jar.set_cookie(_make_cookie("XSRF-TOKEN", "token-123"))
            return _FakeResponse(
                '<script type="application/json" id="__NEXT_DATA__">{}</script>'
                '<script src="/nforms/api/HistoriaPojazdu/1.0.20/resource?uri=main.js"></script>'
            )
        payload = json.loads(request.data.decode("utf-8"))
        assert payload["registrationNumber"] == "DX04419"
        assert payload["VINNumber"] == "VF36D6FZM21283134"
        assert payload["firstRegistrationDate"] == "2005-01-01"
        assert request.headers["X-xsrf-token"] == "token-123"
        assert request.headers["Nf_wid"].startswith("HistoriaPojazdu:")
        if request.full_url.endswith("/vehicle-data"):
            return _FakeResponse('{"technicalData":{"basicData":{"make":"PEUGEOT"}}}')
        if request.full_url.endswith("/autodna-data"):
            return _FakeResponse('{"autoDnaData":{"damaged":false}}')
        if request.full_url.endswith("/carfax-data"):
            return _FakeResponse('{"carfaxData":{"risk":{"stolen":false}}}')
        if request.full_url.endswith("/timeline-data"):
            return _FakeResponse('{"timelineData":{"events":[{"type":"registration"}]}}')
        raise AssertionError(request.full_url)

    opener = _FakeOpener(handler)
    client = VehicleHistoryClient(opener=opener, cookie_jar=jar)

    report = client.fetch_report("DX 04419", " vf36 d6fzm21283134 ", "2005-01-01")

    nf_wid_values = {request.headers["Nf_wid"] for request in opener.requests if "/data/" in request.full_url}
    assert len(nf_wid_values) == 1
    assert report.api_version == "1.0.20"
    assert report.technical_data["technicalData"]["basicData"]["make"] == "PEUGEOT"
    assert report.timeline_data["timelineData"]["events"][0]["type"] == "registration"


def test_fetch_report_retries_on_500_but_not_on_400() -> None:
    jar = CookieJar()
    attempts = {"vehicle-data": 0, "autodna-data": 0, "carfax-data": 0, "timeline-data": 0}

    def handler(request):
        if "engine/ng/index" in request.full_url:
            jar.set_cookie(_make_cookie("XSRF-TOKEN", "token-123"))
            return _FakeResponse('<script src="/nforms/api/HistoriaPojazdu/1.0.20/resource?uri=main.js"></script>')
        endpoint = request.full_url.rsplit("/", 1)[-1]
        attempts[endpoint] += 1
        if endpoint == "vehicle-data" and attempts[endpoint] == 1:
            raise HTTPError(request.full_url, 500, "boom", hdrs=None, fp=None)
        if endpoint == "autodna-data" and attempts[endpoint] == 1:
            return _FakeResponse('{"autoDnaData":{"damaged":false}}')
        if endpoint == "carfax-data" and attempts[endpoint] == 1:
            return _FakeResponse('{"carfaxData":{"risk":{"stolen":false}}}')
        if endpoint == "timeline-data" and attempts[endpoint] == 1:
            return _FakeResponse('{"timelineData":{"events":[{"type":"registration"}]}}')
        if endpoint == "vehicle-data":
            return _FakeResponse('{"technicalData":{"basicData":{"make":"PEUGEOT"}}}')
        raise AssertionError(endpoint)

    client = VehicleHistoryClient(
        opener=_FakeOpener(handler),
        cookie_jar=jar,
        backoff_base_s=0.0,
        retry_attempts=2,
    )
    report = client.fetch_report("DX04419", "VF36D6FZM21283134", "2005-01-01")
    assert report.technical_data["technicalData"]["basicData"]["make"] == "PEUGEOT"
    assert attempts["vehicle-data"] == 2

    attempts_400 = {"vehicle-data": 0}
    jar_400 = CookieJar()

    def handler_400(request):
        if "engine/ng/index" in request.full_url:
            jar_400.set_cookie(_make_cookie("XSRF-TOKEN", "token-123"))
            return _FakeResponse('<script src="/nforms/api/HistoriaPojazdu/1.0.20/resource?uri=main.js"></script>')
        endpoint = request.full_url.rsplit("/", 1)[-1]
        if endpoint == "vehicle-data":
            attempts_400["vehicle-data"] += 1
            raise HTTPError(request.full_url, 406, "nope", hdrs=None, fp=None)
        return _FakeResponse("{}")

    client_400 = VehicleHistoryClient(
        opener=_FakeOpener(handler_400),
        cookie_jar=jar_400,
        backoff_base_s=0.0,
        retry_attempts=3,
    )
    with pytest.raises(RuntimeError, match="HistoriaPojazdu vehicle-data failed with HTTP 406"):
        client_400.fetch_report("DX04419", "VF36D6FZM21283134", "2005-01-01")
    assert attempts_400["vehicle-data"] == 1


def test_fetch_report_treats_optional_external_404_as_unavailable() -> None:
    jar = CookieJar()

    def handler(request):
        if "engine/ng/index" in request.full_url:
            jar.set_cookie(_make_cookie("XSRF-TOKEN", "token-123"))
            return _FakeResponse('<script src="/nforms/api/HistoriaPojazdu/1.0.20/resource?uri=main.js"></script>')
        endpoint = request.full_url.rsplit("/", 1)[-1]
        if endpoint == "vehicle-data":
            return _FakeResponse('{"technicalData":{"basicData":{"make":"PEUGEOT"}}}')
        if endpoint == "timeline-data":
            return _FakeResponse('{"timelineData":{"events":[{"type":"registration"}]}}')
        raise HTTPError(request.full_url, 404, "Not Found", hdrs=None, fp=None)

    client = VehicleHistoryClient(
        opener=_FakeOpener(handler),
        cookie_jar=jar,
        backoff_base_s=0.0,
        retry_attempts=0,
    )

    report = client.fetch_report("DX04419", "VF36D6FZM21283134", "2005-01-01")
    assert report.technical_data["technicalData"]["basicData"]["make"] == "PEUGEOT"
    assert report.autodna_data["unavailable"] is True
    assert report.carfax_data["unavailable"] is True
    assert report.timeline_data["timelineData"]["events"][0]["type"] == "registration"


def test_bootstrap_session_posts_app_request_and_extracts_api_version() -> None:
    jar = CookieJar()

    def handler(request):
        if "engine/ng/index" in request.full_url:
            jar.set_cookie(_make_cookie("XSRF-TOKEN", "token-123"))
            return _FakeResponse(
                '<link href="/nforms/api/HistoriaPojazdu/1.0.20/resource?uri=styles.css" rel="stylesheet" />'
            )
        raise AssertionError(request.full_url)

    opener = _FakeOpener(handler)
    client = VehicleHistoryClient(opener=opener, cookie_jar=jar, retry_attempts=0, backoff_base_s=0.0)

    assert client._bootstrap_session("HistoriaPojazdu:123") == "1.0.20"
    assert [request.method for request in opener.requests] == ["POST"]


def test_bootstrap_session_requires_xsrf_cookie() -> None:
    jar = CookieJar()

    def handler(request):
        if "engine/ng/index" in request.full_url:
            return _FakeResponse('<script src="/nforms/api/HistoriaPojazdu/1.0.21/resource?uri=main.js"></script>')
        raise AssertionError(request.full_url)

    client = VehicleHistoryClient(opener=_FakeOpener(handler), cookie_jar=jar, retry_attempts=0, backoff_base_s=0.0)

    with pytest.raises(RuntimeError, match="did not establish the required HistoriaPojazdu session cookies"):
        client._bootstrap_session("HistoriaPojazdu:123")


def test_bootstrap_session_surfaces_post_transport_error() -> None:
    jar = CookieJar()

    def handler(request):
        if "engine/ng/index" in request.full_url:
            raise HTTPError(request.full_url, 405, "Method Not Allowed", hdrs=None, fp=None)
        raise AssertionError(request.full_url)

    client = VehicleHistoryClient(opener=_FakeOpener(handler), cookie_jar=jar, retry_attempts=0, backoff_base_s=0.0)

    with pytest.raises(RuntimeError, match="bootstrap app failed"):
        client._bootstrap_session("HistoriaPojazdu:123")


def test_bootstrap_session_is_reused_once_explicitly_primed() -> None:
    jar = CookieJar()

    def handler(request):
        if "engine/ng/index" in request.full_url:
            jar.set_cookie(_make_cookie("XSRF-TOKEN", "token-123"))
            return _FakeResponse('<script src="/nforms/api/HistoriaPojazdu/1.0.20/resource?uri=main.js"></script>')
        payload = json.loads(request.data.decode("utf-8"))
        if request.full_url.endswith("/vehicle-data"):
            return _FakeResponse(json.dumps({"technicalData": {"basicData": {"date": payload["firstRegistrationDate"]}}}))
        if request.full_url.endswith("/autodna-data"):
            return _FakeResponse('{"autoDnaData":{}}')
        if request.full_url.endswith("/carfax-data"):
            return _FakeResponse('{"carfaxData":{}}')
        if request.full_url.endswith("/timeline-data"):
            return _FakeResponse('{"timelineData":{"events":[]}}')
        raise AssertionError(request.full_url)

    opener = _FakeOpener(handler)
    client = VehicleHistoryClient(opener=opener, cookie_jar=jar, retry_attempts=0, backoff_base_s=0.0)

    bootstrap = client.bootstrap_session()
    first_report = client.fetch_report("DX04419", "VF36D6FZM21283134", "2005-01-01")
    second_report = client.fetch_report("DX04419", "VF36D6FZM21283134", "2005-01-02")

    bootstrap_requests = [request for request in opener.requests if "engine/ng/index" in request.full_url]
    data_nf_wid_values = {request.headers["Nf_wid"] for request in opener.requests if "/data/" in request.full_url}
    assert len(bootstrap_requests) == 1
    assert data_nf_wid_values == {bootstrap.nf_wid}
    assert first_report.technical_data["technicalData"]["basicData"]["date"] == "2005-01-01"
    assert second_report.technical_data["technicalData"]["basicData"]["date"] == "2005-01-02"


def test_custom_opener_cookie_jar_is_discovered_and_zero_retries_still_runs() -> None:
    opener_jar = CookieJar()
    opener = build_opener(HTTPCookieProcessor(opener_jar))
    provided_jar = CookieJar()

    client = VehicleHistoryClient(opener=opener, cookie_jar=provided_jar, retry_attempts=0, backoff_base_s=0.0)
    client.cookie_jar.set_cookie(_make_cookie("XSRF-TOKEN", "token-123"))

    assert client._cookie_value("XSRF-TOKEN") == "token-123"
    assert any(
        isinstance(handler, HTTPCookieProcessor) and handler.cookiejar is client.cookie_jar
        for handler in opener.handlers
    )

    calls = {"count": 0}

    def action():
        calls["count"] += 1
        return "ok"

    assert _with_retry(action, attempts=0, base_delay=0.0, label="test") == "ok"
    assert calls["count"] == 1


def test_with_retry_handles_connection_level_failures() -> None:
    calls = {"count": 0}

    def action():
        calls["count"] += 1
        if calls["count"] == 1:
            raise http.client.RemoteDisconnected("boom")
        return "ok"

    assert _with_retry(action, attempts=1, base_delay=0.0, label="test") == "ok"
    assert calls["count"] == 2


def test_with_retry_stops_during_backoff_when_cancellation_is_requested() -> None:
    calls = {"count": 0}
    cancel_event = threading.Event()

    def action():
        calls["count"] += 1
        raise TimeoutError("boom")

    def trigger_cancel() -> None:
        time.sleep(0.05)
        cancel_event.set()

    worker = threading.Thread(target=trigger_cancel)
    worker.start()
    with pytest.raises(RuntimeError, match="cancelled"):
        _with_retry(
            action,
            attempts=3,
            base_delay=0.2,
            label="test",
            should_abort=cancel_event.is_set,
        )
    worker.join()
    assert calls["count"] == 1


def test_fetch_report_rejects_non_iso_date_input() -> None:
    client = VehicleHistoryClient(retry_attempts=0, backoff_base_s=0.0)
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        client.fetch_report("DX04419", "VF36D6FZM21283134", "01.01.2005")
