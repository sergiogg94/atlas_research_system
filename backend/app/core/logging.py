import logging
import logging.config
from contextlib import contextmanager
from contextvars import ContextVar

import colorlog
from app.config import get_settings

trace_id_var: ContextVar[str] = ContextVar("trace_id", default="")
agent_name_var: ContextVar[str] = ContextVar("agent_name", default="")


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
