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
from bidict import bidict

from ._canvas import CanvasSync
from ._config import Config
from ._grit import Grit

if TYPE_CHECKING:
    from types import FrameType


logger = logging.getLogger("sync")


def setup_logging() -> None:
    config_file = Path("configs/sync_logging_config.json")
    with config_file.open() as f:
        config = json.load(f)
    logging.config.dictConfig(config)


def write_timestamped_file(
    filepath: Path,
    data: str,
    concatenator: str = "_",
) -> None:
    """Write the given data to a new file with a timestamped name.

    Args:
    ----
        filepath (Path): The path of the file to be written.
        data (str): The data to be written to the file.
        concatenator (str, optional): The string to concatenate between the original
        file name and the timestamp. Defaults to "_".

    Returns:
    -------
        None: This function does not return anything.

    Example:
    -------
        >>> filepath = Path("example.txt")
        >>> data = "Hello, world!"
        >>> write_timestamped_file(filepath, data)
        Creates a new file named "example_2022_01_01_12_00.txt" with the content
        "Hello, world!".

    """
    timestamp = datetime.now(timezone.utc).strftime("%Y_%m_%d_%H_%M")
    no_ext = filepath.with_suffix("")
    ext = filepath.suffix
    new_name = Path(f"{no_ext}{concatenator}{timestamp}{ext}")
    new_name.write_text(data)


def main() -> None:
    setup_logging()

    logger.debug("Loading in config file")

    with Path("configs/sync_config.toml").open("rb") as f:
        config = Config.model_validate(tomllib.load(f))

    logger.debug("Loaded sync config contents: %s", config)

    upload_to_grit = config.grit.perform_upload
    backup_folder = config.misc.backup_folder

    grit = Grit(config.grit.api_url, config.grit.api_key)
    canvas = CanvasSync(
        config.canvas.api_url,
        config.canvas.api_key,
        config.canvas.course_id,
        bidict(config.canvas.quizzes),
    )

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
