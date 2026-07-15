import logging
import logging.config
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime
from zoneinfo import ZoneInfo

import colorlog

from app.config import get_settings

trace_id_var: ContextVar[str] = ContextVar("trace_id", default="")
agent_name_var: ContextVar[str] = ContextVar("agent_name", default="")
execution_id_var: ContextVar[str] = ContextVar("execution_id", default="")
step_id_var: ContextVar[str | None] = ContextVar("step_id", default=None)


@contextmanager
def trace_context(trace_id: str, agent_name: str):
    token_trace = trace_id_var.set(trace_id)
    token_agent = agent_name_var.set(agent_name)
    try:
        yield
    finally:
        trace_id_var.reset(token_trace)
        agent_name_var.reset(token_agent)


settings = get_settings()


class ContextFormatter(colorlog.ColoredFormatter):
    def formatTime(self, record, datefmt=None):
        dt = datetime.fromtimestamp(record.created, tz=ZoneInfo(settings.timezone))
        return dt.strftime(datefmt or "%Y-%m-%d %H:%M:%S")

    def format(self, record):
        record.trace_id = trace_id_var.get() or "-"
        record.agent_name = agent_name_var.get() or "-"
        return super().format(record)


custom_dict = {
    "version": 1,
    "formatters": {
        "default": {
            "()": ContextFormatter,
            "format": "%(log_color)s%(levelname)-4s%(reset)s [%(trace_id)s] [%(agent_name)s] (%(asctime)s) (%(module)s %(funcName)s): %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "default",
        }
    },
    "loggers": {
        "": {
            "handlers": ["console"],
            "level": settings.log_level,
        }
    },
}

logging.config.dictConfig(custom_dict)

logger = logging.getLogger(__name__)


def trace_step(agent_name: str):
    """Decorator that logs latency and captures step telemetry for agent nodes."""
    import functools
    import time

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(state, *args, **kwargs):
            trace_id = state.get("trace_id") or trace_id_var.get()
            agent_name_var.set(agent_name)
            start = time.monotonic()
            try:
                result = await func(state, *args, **kwargs)
                elapsed_ms = int((time.monotonic() - start) * 1000)
                logger.info(
                    "%s completed in %dms",
                    agent_name,
                    elapsed_ms,
                    extra={"latency_ms": elapsed_ms, "trace_id": trace_id},
                )
                return {**result, "last_step_latency_ms": elapsed_ms}
            except Exception as e:
                elapsed_ms = int((time.monotonic() - start) * 1000)
                logger.error(
                    "%s failed after %dms: %s",
                    agent_name,
                    elapsed_ms,
                    str(e),
                    extra={"latency_ms": elapsed_ms, "trace_id": trace_id},
                )
                raise

        return wrapper

    return decorator
