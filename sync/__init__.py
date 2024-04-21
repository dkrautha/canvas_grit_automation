"""Grit Sync."""

from __future__ import annotations

import json
import logging
import logging.config
import signal
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Never

import tomllib
from apscheduler.schedulers.background import BlockingScheduler

from ._canvas import CanvasSync
from ._config import Config
from ._grit import Grit

if TYPE_CHECKING:
    from types import FrameType


with Path("configs/sync_config.toml").open("rb") as f:
    sync_config = Config.model_validate(tomllib.load(f))

logger = logging.getLogger("sync")


def setup_logging() -> None:
    config_file = Path(sync_config.misc.logging_config_file)
    with config_file.open() as f:
        config = json.load(f)
    logging.config.dictConfig(config)


def write_timestamped_file(
    filepath: Path,
    data: str,
    concatenator: str = "_",
) -> None:
    timestamp = datetime.now(timezone.utc).strftime("%Y_%m_%d_%H_%M")
    no_ext = filepath.with_suffix("")
    ext = filepath.suffix
    new_name = Path(f"{no_ext}{concatenator}{timestamp}{ext}")
    new_name.write_text(data)


def main() -> None:
    setup_logging()

    upload_to_grit = sync_config.grit.perform_upload
    backup_folder = sync_config.misc.backup_folder

    grit = Grit(sync_config.grit.api_url, sync_config.grit.api_key)
    canvas = CanvasSync(sync_config.canvas)

    def run() -> None:
        data = canvas.get_passing_results()

        if upload_to_grit and len(data) > 0:
            response = grit.upsert(data)
            if not response.ok:
                logger.warning("Request to Grit didn't return OK")
                logger.warning(response.text)

        logger.info("Pulling new backup from Grit now")
        backup = grit.get_backup()
        write_timestamped_file(backup_folder / "grit_export.csv", backup.write_csv())
        logger.info("Backup pull complete")

    scheduler = BlockingScheduler()

    def signal_handler(signal_num: int, _frame: FrameType | None) -> Never:
        signal_name = signal.Signals(signal_num).name
        logging.getLogger("grit").info(f"Shutting down due to signal {signal_name}")
        if scheduler.running:
            scheduler.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    run()

    scheduler.add_job(run, "interval", minutes=30)
    scheduler.start()


__all__ = []
