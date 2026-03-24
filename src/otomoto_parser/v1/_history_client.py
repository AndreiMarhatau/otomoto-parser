from __future__ import annotations

import json
import time
from datetime import date, datetime
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request

from ._history_common import (
    DATA_ENDPOINTS,
    INIT_URL,
    CancellationRequested,
    RetrySettings,
    VehicleHistoryClientConfig,
    VehicleHistoryBootstrap,
    VehicleHistoryReport,
    _error_detail,
    _extract_api_version,
    _normalize_first_registration_date,
    _normalize_registration_number,
    _normalize_vin_number,
    _with_retry,
)
from ._history_transport import _bootstrap_headers, _build_opener_with_cookies, _data_headers, _discover_cookie_jar


class VehicleHistoryClient:
    def __init__(self, config: VehicleHistoryClientConfig | None = None, **legacy_kwargs: Any) -> None:
        resolved = _resolve_client_config(config, legacy_kwargs)
        self.cookie_jar = _discover_cookie_jar(resolved.opener, resolved.cookie_jar)
        self.opener = _build_opener_with_cookies(resolved.opener, self.cookie_jar)
        self.user_agent = resolved.user_agent
        self.accept_language = resolved.accept_language
        self.timeout_s = resolved.timeout_s
        self.retry_attempts = resolved.retry_attempts
        self.backoff_base_s = resolved.backoff_base_s
        self.cancel_event = resolved.cancel_event
        self._bootstrap_context: VehicleHistoryBootstrap | None = None

    def bootstrap_session(self, *, force: bool = False) -> VehicleHistoryBootstrap:
        if self._bootstrap_context is not None and not force:
            return self._bootstrap_context
        self._raise_if_cancelled()
        context = VehicleHistoryBootstrap(
            nf_wid=f"HistoriaPojazdu:{int(time.time() * 1000)}",
            api_version="",
            xsrf_token="",
        )
        api_version = self._bootstrap_session(context.nf_wid)
        self._bootstrap_context = VehicleHistoryBootstrap(
            nf_wid=context.nf_wid,
            api_version=api_version,
            xsrf_token=self._cookie_value("XSRF-TOKEN"),
        )
        return self._bootstrap_context

    def fetch_report(
        self,
        registration_number: str,
        vin_number: str,
        first_registration_date: str | date | datetime,
    ) -> VehicleHistoryReport:
        payload = {
            "registrationNumber": _normalize_registration_number(registration_number),
            "VINNumber": _normalize_vin_number(vin_number),
            "firstRegistrationDate": _normalize_first_registration_date(first_registration_date),
        }
        bootstrap = self.bootstrap_session()
        responses = {endpoint: self._fetch_endpoint(bootstrap, endpoint, payload) for endpoint in DATA_ENDPOINTS}
        return VehicleHistoryReport(
            registration_number=payload["registrationNumber"],
            vin_number=payload["VINNumber"],
            first_registration_date=payload["firstRegistrationDate"],
            api_version=bootstrap.api_version,
            technical_data=responses["vehicle-data"],
            autodna_data=responses["autodna-data"],
            carfax_data=responses["carfax-data"],
            timeline_data=responses["timeline-data"],
        )

    def _fetch_endpoint(
        self,
        bootstrap: VehicleHistoryBootstrap,
        endpoint: str,
        payload: dict[str, str],
    ) -> dict[str, Any]:
        self._raise_if_cancelled()
        try:
            return self._post_data({"api_version": bootstrap.api_version, "endpoint": endpoint, "nf_wid": bootstrap.nf_wid, "xsrf_token": bootstrap.xsrf_token, "payload": payload})
        except HTTPError as exc:
            if endpoint in {"autodna-data", "carfax-data"} and exc.code == 404:
                return {"unavailable": True, "status": exc.code, "message": "This external report is not available for the vehicle."}
            raise RuntimeError(f"HistoriaPojazdu {endpoint} failed with HTTP {exc.code}: {_error_detail(exc)}") from exc
        except Exception as exc:
            raise RuntimeError(f"HistoriaPojazdu {endpoint} failed: {exc}") from exc

    def _bootstrap_session(self, nf_wid: str) -> str:
        request = Request(
            INIT_URL,
            data=urlencode({"NF_WID": nf_wid}).encode("utf-8"),
            method="POST",
            headers=_bootstrap_headers(self.accept_language, self.user_agent),
        )
        try:
            html = _with_retry(
                lambda: self._read_text(request),
                RetrySettings(
                    attempts=self.retry_attempts,
                    base_delay=self.backoff_base_s,
                    label="HistoriaPojazdu bootstrap app",
                    should_abort=self._is_cancelled,
                ),
            )
        except CancellationRequested:
            raise
        except (HTTPError, URLError, TimeoutError, ConnectionResetError) as exc:
            raise RuntimeError(f"HistoriaPojazdu bootstrap app failed: {exc}") from exc
        api_version = _extract_api_version(html)
        if not self._has_cookie("XSRF-TOKEN"):
            raise RuntimeError("HistoriaPojazdu bootstrap app did not establish the required HistoriaPojazdu session cookies.")
        return api_version

    def _post_data(self, request_data: dict[str, Any]) -> dict[str, Any]:
        request = Request(
            f"https://moj.gov.pl/nforms/api/HistoriaPojazdu/{request_data['api_version']}/data/{request_data['endpoint']}",
            data=json.dumps(request_data["payload"]).encode("utf-8"),
            method="POST",
            headers=_data_headers(self.accept_language, self.user_agent, request_data["nf_wid"], request_data["xsrf_token"]),
        )
        return _with_retry(
            lambda: json.loads(self._read_text(request)),
            RetrySettings(
                attempts=self.retry_attempts,
                base_delay=self.backoff_base_s,
                label=f"HistoriaPojazdu {request_data['endpoint']}",
                should_abort=self._is_cancelled,
            ),
        )

    def _read_text(self, request: Request) -> str:
        self._raise_if_cancelled()
        with self.opener.open(request, timeout=self.timeout_s) as response:
            return response.read().decode("utf-8")

    def _cookie_value(self, name: str) -> str:
        for cookie in self.cookie_jar:
            if cookie.name == name:
                return cookie.value
        raise RuntimeError(f"Missing required cookie: {name}")

    def _has_cookie(self, name: str) -> bool:
        return any(cookie.name == name and cookie.value for cookie in self.cookie_jar)

    def _is_cancelled(self) -> bool:
        return self.cancel_event.is_set() if self.cancel_event is not None else False

    def _raise_if_cancelled(self) -> None:
        if self._is_cancelled():
            raise CancellationRequested("HistoriaPojazdu request cancelled.")


def _resolve_client_config(
    config: VehicleHistoryClientConfig | None,
    legacy_kwargs: dict[str, Any],
) -> VehicleHistoryClientConfig:
    if config is None:
        return VehicleHistoryClientConfig(**legacy_kwargs)
    if legacy_kwargs:
        raise TypeError("VehicleHistoryClient accepts either config or legacy keyword arguments, not both.")
    return config
