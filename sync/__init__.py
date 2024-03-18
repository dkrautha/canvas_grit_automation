"""Grit Sync."""

from __future__ import annotations

import io
import logging
import signal
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Never, cast

import polars as pl
import requests
import tomllib
from apscheduler.schedulers.background import BlockingScheduler
from canvasapi import Canvas

from ._config import Config

if TYPE_CHECKING:
    from types import FrameType

    from canvasapi.course import Course

with Path("config.toml").open("rb") as f:
    CONFIG = Config.model_validate(tomllib.load(f))

QUIZ_NAME_TO_IDS = CONFIG.canvas.quizzes
QUIZ_IDS_TO_NAME = {value: key for key, value in QUIZ_NAME_TO_IDS.items()}
COURSE_ID = CONFIG.canvas.course_id
API_URL = CONFIG.canvas.api_url
API_KEY = CONFIG.canvas.api_key
GRIT_URL = CONFIG.grit.api_url
GRIT_API_KEY = CONFIG.grit.api_key
UPLOAD_TO_GRIT = CONFIG.grit.perform_upload
LOG_FOLDER = CONFIG.misc.log_folder
BACKUP_FOLDER = CONFIG.misc.backup_folder


# TODO(David): refactor this to a config file and use modern logging practices
# https://www.youtube.com/watch?v=9L77QExPmI0
def setup_logging() -> None:
    logger = logging.getLogger("grit")
    logger.setLevel(logging.DEBUG)

    timestamp = datetime.now(timezone.utc).strftime("%Y_%m_%d")
    filepath = LOG_FOLDER / f"{timestamp}.txt"
    filepath.touch()

    file_handle = logging.FileHandler(filepath)
    file_handle.setLevel(logging.DEBUG)

    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setLevel(logging.INFO)

    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    logger.addHandler(file_handle)
    logger.addHandler(stderr_handler)


# TODO(David): uses globals, should they be made to be parameters?
def get_quiz_results(
    course: Course,
    program_start: datetime,
) -> pl.DataFrame:
    logger = logging.getLogger("grit")

    submissions = course.get_multiple_submissions(
        assignment_ids=QUIZ_NAME_TO_IDS.values(),
        submitted_since=program_start - timedelta(days=7),
        student_ids=["all"],
    )

    logger.info("Received submissions from Canvas")

    schema = {
        "firstName": pl.Utf8,
        "lastName": pl.Utf8,
        "externalId": pl.Utf8,
        "email": pl.Utf8,
        **{quiz_name: pl.Utf8 for quiz_name in QUIZ_NAME_TO_IDS},
    }

    passing = pl.DataFrame(schema=schema)
    passing_score = 90

    for sub in submissions:
        if sub.grade is None:
            continue

        grade = float(cast(str, sub.grade).replace("%", ""))
        if grade < passing_score:
            continue

        quiz_name = QUIZ_IDS_TO_NAME[sub.assignment_id]
        user_id = sub.user_id
        student = course.get_user(user_id)
        last_name, first_name = cast(
            tuple[str, str],
            [n.strip() for n in student.sortable_name.split(",")],
        )
        cwid: str = student.sis_user_id
        email: str = student.login_id

        logger.debug(
            "received submission %s %s %s %s %s %s",
            quiz_name,
            cwid,
            first_name,
            last_name,
            grade,
            email,
        )

        row = pl.DataFrame(
            {
                "firstName": first_name,
                "lastName": last_name,
                "externalId": cwid,
                "email": email,
                **{q: "x" if q == quiz_name else "" for q in QUIZ_NAME_TO_IDS},
            },
        )
        passing = passing.vstack(row)

    logger.info("Processed submissions")

    # TODO(David): name this better
    gb = ["firstName", "lastName", "externalId", "email"]
    quiz_cols = pl.all().exclude(gb)
    passing = passing.group_by(gb).agg(quiz_cols.str.concat(""))
    return passing.with_columns(
        [
            pl.when(quiz_cols.str.len_bytes() == 0)
            .then(pl.lit(None))
            .otherwise(pl.lit("x"))
            .name.keep(),
        ],
    )


# TODO(David): function name sounds kinda jank
def upsert_grit(file: io.BytesIO) -> requests.Response:
    session = requests.Session()
    request = session.prepare_request(
        requests.Request(
            method="POST",
            url=f"{GRIT_URL}/api/batch/user/upsert",
            # url=f"{GRIT_URL}/api/batch/user/upsert?",
            # "processPermissionGroups=true&"
            # "processRFiDCards=false&"
            # "processDemographics=false&"
            # "processAccessTimes=true&"
            # "processMobileGritCard=false",
            headers={"x-auth-token": GRIT_API_KEY},
            files={"file": ("upload.csv", file.getvalue(), "text/csv")},
        ),
    )
    return session.send(request)


def process_data(program_start: datetime) -> pl.DataFrame:
    canvas = Canvas(API_URL, API_KEY)

    course = canvas.get_course(COURSE_ID)
    return get_quiz_results(course, program_start).with_columns(
        pl.lit("x").alias("at:Any Time"),
        active=pl.lit("x"),
    )


def send_data_to_grit(df: pl.DataFrame) -> None:
    logger = logging.getLogger("grit")

    if len(df) == 0:
        logger.info("No new submissions received, not sending to Grit")
        return

    grit_csv = io.BytesIO()
    df.write_csv(grit_csv)
    logger.debug(f"CSV to send:\n{grit_csv.getvalue().decode('utf-8')}")

    if UPLOAD_TO_GRIT:
        logger.info("Sending data to Grit")
        response = upsert_grit(grit_csv)
        if not response.ok:
            logger.warning("Request to Grit didn't return OK")
            logger.warning(response.text)


def pull_backup() -> None:
    session = requests.Session()
    request = session.prepare_request(
        requests.Request(
            method="GET",
            url=f"{GRIT_URL}/api/batch/user/export",
            headers={"x-auth-token": GRIT_API_KEY},
        ),
    )
    response = session.send(request)
    as_excel = io.BytesIO(response.content)

    timestamp = datetime.now(timezone.utc).strftime("%Y_%m_%d_%H_%M")
    filepath = BACKUP_FOLDER / f"grit_export_{timestamp}.csv"
    filepath.touch()
    pl.read_excel(as_excel).write_csv(filepath)


def main() -> None:
    def run() -> None:
        setup_logging()

        logger = logging.getLogger("grit")
        program_start = datetime.now(timezone.utc)

        logger.info(f"Starting at {program_start}\n")

        data = process_data(program_start)
        send_data_to_grit(data)

        logger.info("Pulling new backup from Grit now")
        pull_backup()
        logger.info("Backup pull complete")

    setup_logging()

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
