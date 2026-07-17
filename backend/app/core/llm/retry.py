import logging
from typing import Any, cast

import httpx
from tenacity import (
    before_sleep_log,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)
from tenacity._utils import LoggerProtocol

from app.core.logging import logger


def _before(retry_state):
    try:
        fname = retry_state.fn.__name__
    except Exception:
        fname = str(retry_state.fn)
    logger.info("Retry starting: fn=%s attempt=%s", fname, retry_state.attempt_number)


def _after(retry_state):
    try:
        fname = retry_state.fn.__name__
    except Exception:
        fname = str(retry_state.fn)

    exc = None
    if retry_state.outcome:
        try:
            exc = retry_state.outcome.exception()
        except Exception:
            exc = None

    if exc:
        logger.warning(
            "Retry attempt %s for %s failed: %s",
            retry_state.attempt_number,
            fname,
            exc,
        )
    else:
        logger.info("Retry attempt %s for %s completed", retry_state.attempt_number, fname)


retry_config: dict[str, Any] = {
    "stop": stop_after_attempt(3),
    "wait": wait_exponential(multiplier=1, min=2, max=10),
    "retry": retry_if_exception_type(
        (
            httpx.TimeoutException,
            httpx.NetworkError,
        )
    ),
    "reraise": True,
    "before": _before,
    "after": _after,
    "before_sleep": before_sleep_log(cast(LoggerProtocol, logger), logging.WARNING),
}
