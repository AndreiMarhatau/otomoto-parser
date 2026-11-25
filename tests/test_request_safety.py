from fastapi.testclient import TestClient

from otomoto_parser.v2.app import create_app


def test_app_no_longer_uses_the_access_code_file(tmp_path):
    (tmp_path / "access.json").write_text("no longer read")
    with TestClient(create_app(data_dir=tmp_path)) as client:
        assert client.get("/openapi.json").status_code == 200
        assert client.get("/api/access").status_code == 404


def test_browser_mutations_still_require_a_same_origin(tmp_path):
    app = create_app(data_dir=tmp_path)

    @app.post("/api/request-safety-test")
    def mutate():
        return {"ok": True}

    with TestClient(app) as client:
        for origin in ("https://cross-origin.example", "null"):
            response = client.post("/api/request-safety-test", headers={"origin": origin})
            assert response.status_code == 403
        for origin in ("http://testserver", "https://testserver"):
            response = client.post("/api/request-safety-test", headers={"origin": origin})
            assert response.status_code == 200
        assert client.post("/api/request-safety-test").status_code == 200
