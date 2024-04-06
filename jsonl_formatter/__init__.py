""""""

from __future__ import annotations

import datetime as dt
import json
import logging
from typing import Self, override


class JsonlFormatter(logging.Formatter):
    """"""

    fmt_keys: dict[str, str]

    def __init__(self, *, fmt_keys: dict[str, str] | None = None) -> None:
        """"""

        super().__init__()
        self.fmt_keys = fmt_keys or {}

    @override
    def format(self: Self, record: logging.LogRecord) -> str:
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

        return message
