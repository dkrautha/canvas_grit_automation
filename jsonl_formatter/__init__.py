"""A logging formatter that outputs logs in jsonl format.

Credit goes to James Murphy of mCoding, this implementation
is heavily based on his work.
https://github.com/mCodingLLC/VideosSampleCode/blob/master/videos/135_modern_logging/mylogger.py
"""

from __future__ import annotations

import datetime as dt
import json
import logging
from typing import Self, override

LOG_RECORD_BUILTIN_ATTRS = {
    "args",
    "asctime",
    "created",
    "exc_info",
    "exc_text",
    "filename",
    "funcName",
    "levelname",
    "levelno",
    "lineno",
    "module",
    "msecs",
    "message",
    "msg",
    "name",
    "pathname",
    "process",
    "processName",
    "relativeCreated",
    "stack_info",
    "thread",
    "threadName",
    "taskName",
}


class JsonlFormatter(logging.Formatter):
    """A logging formatter that outputs logs in jsonl format.

    The formatter takes a dict of str to str, which maps output field
    names to attribute names on the LogRecord. If an attribute is not
    found on the LogRecord, the LogRecord's __dict__ is checked for a
    matching key. The builtin attributes from the LogRecord are not
    included in the output.

    The fields always included in the output are the message, timestamp,
    and exc_info (if present).
    """

    fmt_keys: dict[str, str]

    def __init__(self: Self, *, fmt_keys: dict[str, str] | None = None) -> None:
        """Initialize the formatter.

        Args:
        ----
            fmt_keys: A dict mapping output field names to LogRecord
                attribute names. If not provided, an empty dict is used.

        """
        super().__init__()
        self.fmt_keys = fmt_keys or {}

    @override
    def format(self: Self, record: logging.LogRecord) -> str:
        """Format a LogRecord into a jsonl string.

        Args:
        ----
            record: The LogRecord to format.

        Returns:
        -------
            A jsonl string representing the LogRecord.

        """
        message = self._prepare_log_dict(record)
        return json.dumps(message, default=str)

    def _prepare_log_dict(self: Self, record: logging.LogRecord) -> dict[str, str]:
        always_fields = {
            "message": record.getMessage(),
            "timestamp": dt.datetime.fromtimestamp(
                record.created,
                tz=dt.timezone.utc,
            ).isoformat(),
        }

        if record.exc_info:
            always_fields["exc_info"] = self.formatException(record.exc_info)

        if record.stack_info:
            always_fields["stack_info"] = self.formatStack(record.stack_info)

        message = {
            key: msg_val
            if (msg_val := always_fields.pop(val, None)) is not None
            else getattr(record, val)
            for key, val in self.fmt_keys.items()
        }
        message.update(always_fields)

        for key, val in record.__dict__.items():
            if key not in LOG_RECORD_BUILTIN_ATTRS:
                message[key] = val

        return message


__all__ = ["JsonlFormatter"]
