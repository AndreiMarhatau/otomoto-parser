from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from otomoto_parser.v2 import app as app_module
from otomoto_parser.v2._app_frontend import mount_frontend, register_geocode_routes
from otomoto_parser.v2._app_geocode import _GEOCODE_CACHE, geocode_location


class _UrlOpenResponse:
    def __init__(self, payload: list[dict[str, str]]) -> None:
        self._payload = payload

    def __enter__(self) -> "_UrlOpenResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")


def test_geocode_location_caches_successful_results(monkeypatch) -> None:
    _GEOCODE_CACHE.clear()
    calls: list[str] = []

    def fake_urlopen(request, timeout: int):
        calls.append(f"{request.full_url}|{timeout}")
        return _UrlOpenResponse([{"lat": "52.2297", "lon": "21.0122", "display_name": "Warsaw, Poland"}])

    monkeypatch.setattr("otomoto_parser.v2._app_geocode.urlopen", fake_urlopen)

    first = geocode_location("Warsaw")
    second = geocode_location("Warsaw")

    assert first == {"lat": 52.2297, "lon": 21.0122, "label": "Warsaw, Poland"}
    assert second == first
    assert len(calls) == 1


def test_geocode_location_handles_empty_and_errors(monkeypatch) -> None:
    _GEOCODE_CACHE.clear()
    monkeypatch.setattr("otomoto_parser.v2._app_geocode.urlopen", lambda request, timeout: _UrlOpenResponse([]))
    assert geocode_location("Unknown") is None

    def raising_urlopen(request, timeout: int):
        raise TimeoutError("boom")

    monkeypatch.setattr("otomoto_parser.v2._app_geocode.urlopen", raising_urlopen)
    try:
        geocode_location("Timeout")
    except RuntimeError as exc:
        assert str(exc) == "Could not load map preview."
    else:
        raise AssertionError("Expected geocode_location to raise RuntimeError.")


def test_frontend_routes_mount_and_geocode(tmp_path: Path, monkeypatch) -> None:
    app = FastAPI()
    dist_dir = tmp_path / "dist"
    assets_dir = dist_dir / "assets"
    assets_dir.mkdir(parents=True)
    (dist_dir / "index.html").write_text("<html>spa</html>", encoding="utf-8")
    (assets_dir / "app.txt").write_text("asset", encoding="utf-8")

    def fake_geocode(query: str):
        if query == "fail":
            raise RuntimeError("lookup failed")
        return {"label": query, "lat": 1.0, "lon": 2.0}

    monkeypatch.setattr(app_module, "geocode_location", fake_geocode)
    register_geocode_routes(app)
    mount_frontend(app, dist_dir)

    with TestClient(app) as client:
        assert client.get("/api/geocode", params={"query": "Warsaw"}).json() == {"item": {"label": "Warsaw", "lat": 1.0, "lon": 2.0}}
        assert client.post("/api/geocode/batch", json={"queries": ["Warsaw", "", "Warsaw", "Krakow"]}).json() == {
            "items": {
                "Warsaw": {"label": "Warsaw", "lat": 1.0, "lon": 2.0},
                "Krakow": {"label": "Krakow", "lat": 1.0, "lon": 2.0},
            }
        }
        assert client.get("/api/geocode", params={"query": "fail"}).status_code == 502
        assert client.get("/assets/app.txt").text == "asset"
        assert client.get("/results").text == "<html>spa</html>"
        assert client.get("/api/unknown").status_code == 404


def test_app_main_runs_uvicorn(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class _Parser:
        def parse_args(self):
            return SimpleNamespace(
                data_dir="/tmp/app-data",
                host="0.0.0.0",
                port=9000,
                retries=5,
                backoff=2.0,
                delay_min=0.5,
                delay_max=1.5,
                request_timeout_s=30.0,
            )

    monkeypatch.setattr(app_module, "build_arg_parser", lambda: _Parser())
    monkeypatch.setattr(app_module, "create_app", lambda **kwargs: ("fake-app", kwargs))
    monkeypatch.setitem(sys.modules, "uvicorn", SimpleNamespace(run=lambda app, host, port: captured.update({"app": app, "host": host, "port": port})))

    app_module.main()

    assert captured == {
        "app": ("fake-app", {
            "data_dir": Path("/tmp/app-data"),
            "parser_options": {
                "retry_attempts": 5,
                "backoff_base": 2.0,
                "delay_min": 0.5,
                "delay_max": 1.5,
                "request_timeout_s": 30.0,
            },
        }),
        "host": "0.0.0.0",
        "port": 9000,
    }
