from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Callable, TypeVar
from urllib.error import HTTPError, URLError


T = TypeVar("T")


@dataclass(frozen=True)
class RetryPolicy:
    attempts: int
    base_delay: float


def _with_retry(
    action: Callable[[], T],
    policy: RetryPolicy,
    label: str | None = None,
    logger: logging.Logger | None = None,
) -> T:
    last_error: Exception | None = None
    for attempt in range(policy.attempts):
        try:
            return action()
        except (HTTPError, URLError, TimeoutError, RuntimeError) as exc:
            last_error = exc
            if attempt == policy.attempts - 1:
                break
            delay = policy.base_delay * (2**attempt)
            if logger is not None and label is not None:
                logger.warning(
                    "Retrying %s after error (%s: %s). Attempt %s/%s in %.2fs.",
                    label,
                    exc.__class__.__name__,
                    str(exc),
                    attempt + 1,
                    policy.attempts,
                    delay,
                )
            time.sleep(delay)
    if last_error is not None:
        raise last_error
    raise RuntimeError("Retry failed without exception")
