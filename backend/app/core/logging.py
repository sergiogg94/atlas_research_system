import logging
import logging.config

import colorlog
from app.config import get_settings

settings = get_settings()

custom_dict = {
    "version": 1,
    "formatters": {
        "default": {
            "()": colorlog.ColoredFormatter,
            "format": "%(log_color)s%(levelname)-4s%(reset)s (%(asctime)s) (%(module)s %(funcName)s): %(message)s",
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
