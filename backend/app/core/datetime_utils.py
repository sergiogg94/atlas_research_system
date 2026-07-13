from datetime import datetime
from zoneinfo import ZoneInfo

from app.config import get_settings


def now() -> datetime:
    return datetime.now(ZoneInfo(get_settings().timezone))
