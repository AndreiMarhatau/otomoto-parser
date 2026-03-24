from __future__ import annotations

from urllib.error import URLError

import pytest

from otomoto_parser.v1._parser_retry import RetryPolicy, _with_retry


def test_with_retry_retries_logs_and_sleeps(monkeypatch: pytest.MonkeyPatch) -> None:
    attempts = {"count": 0}
    sleep_calls: list[float] = []
    warning_calls: list[tuple[object, ...]] = []
    monkeypatch.setattr("otomoto_parser.v1._parser_retry.time.sleep", lambda delay: sleep_calls.append(delay))

    class LoggerStub:
        def warning(self, *args: object) -> None:
            warning_calls.append(args)

    def flaky_action() -> str:
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise URLError("temporary")
        return "ok"

    result = _with_retry(flaky_action, RetryPolicy(attempts=3, base_delay=0.5), label="graphql", logger=LoggerStub())

    assert result == "ok"
    assert sleep_calls == [0.5]
    assert len(warning_calls) == 1


def test_with_retry_raises_last_error_after_exhausting_attempts(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("otomoto_parser.v1._parser_retry.time.sleep", lambda delay: None)

    with pytest.raises(TimeoutError, match="still failing"):
        _with_retry(
            lambda: (_ for _ in ()).throw(TimeoutError("still failing")),
            RetryPolicy(attempts=2, base_delay=0.1),
        )


def test_with_retry_rejects_zero_attempt_policy() -> None:
    with pytest.raises(RuntimeError, match="Retry failed without exception"):
        _with_retry(lambda: "never called", RetryPolicy(attempts=0, base_delay=0.1))
