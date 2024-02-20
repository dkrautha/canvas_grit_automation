import io
import signal
import sys
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import cast

import polars as pl
import requests
from apscheduler.schedulers.background import BlockingScheduler
from canvasapi import Canvas
from canvasapi.course import Course

from .env import get_env_or_raise, get_quiz_ids

QUIZ_NAME_TO_IDS = get_quiz_ids()
QUIZ_IDS_TO_NAME = {v: k for k, v in QUIZ_NAME_TO_IDS.items()}
API_URL = get_env_or_raise("CANVAS_API_URL")
API_KEY = get_env_or_raise("CANVAS_API_KEY")
GRIT_URL = get_env_or_raise("GRIT_URL")
GRIT_API_KEY = get_env_or_raise("GRIT_API_KEY")
UPLOAD_TO_GRIT = get_env_or_raise("UPLOAD_TO_GRIT") == "true"
LOG_FOLDER = Path(get_env_or_raise("LOG_FOLDER"))
BACKUP_FOLDER = Path(get_env_or_raise("BACKUP_FOLDER"))


# TODO: refactor this to a config file and use modern logging practices
# https://www.youtube.com/watch?v=9L77QExPmI0
def setup_logging():
    logger = logging.getLogger("grit")
    logger.setLevel(logging.DEBUG)

    timestamp = datetime.now().strftime("%Y_%m_%d")
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


# TODO: uses globals, should they be made to be parameters?
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

    SCHEMA = {
        "firstName": pl.Utf8,
        "lastName": pl.Utf8,
        "externalId": pl.Utf8,
        "email": pl.Utf8,
        **{quiz_name: pl.Utf8 for quiz_name in QUIZ_NAME_TO_IDS.keys()},
    }

    df = pl.DataFrame(schema=SCHEMA)

    for sub in submissions:
        if sub.grade is None:
            continue

        grade = float(cast(str, sub.grade).replace("%", ""))
        if grade < 90:
            continue

        quiz_name = QUIZ_IDS_TO_NAME[sub.assignment_id]
        user_id = sub.user_id
        student = course.get_user(user_id)
        last_name, first_name = cast(
            tuple[str, str], [n.strip() for n in student.sortable_name.split(",")]
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
                **{q: "x" if q == quiz_name else "" for q in QUIZ_NAME_TO_IDS.keys()},
            },
        )
        df = df.vstack(row)

    logger.info("Processed submissions")

    # TODO: name this better
    gb = ["firstName", "lastName", "externalId", "email"]
    quiz_cols = pl.all().exclude(gb)
    df = df.group_by(gb).agg(quiz_cols.str.concat(""))
    df = df.with_columns(
        [
            pl.when(quiz_cols.str.len_bytes() == 0)
            .then(pl.lit(None))
            .otherwise(pl.lit("x"))
            .name.keep()
        ]
    )

    return df


# TODO: function name sounds kinda jank
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
        )
    )
    response = session.send(request)
    return response


def process_data(program_start: datetime) -> pl.DataFrame:
    canvas = Canvas(API_URL, API_KEY)

    course_id = get_env_or_raise("CANVAS_COURSE_ID")
    course = canvas.get_course(course_id)
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


def pull_backup():
    session = requests.Session()
    request = session.prepare_request(
        requests.Request(
            method="GET",
            url=f"{GRIT_URL}/api/batch/user/export",
            headers={"x-auth-token": GRIT_API_KEY},
        )
    )
    response = session.send(request)
    as_excel = io.BytesIO(response.content)

    timestamp = datetime.now().strftime("%Y_%m_%d_%H_%M")
    filepath = BACKUP_FOLDER / f"grit_export_{timestamp}.csv"
    filepath.touch()
    pl.read_excel(as_excel).write_csv(filepath)


def main():
    def run():
        setup_logging()

        logger = logging.getLogger("grit")
        program_start = datetime.now(timezone.utc)

        logger.info(f"Starting at {program_start}\n")

        df = process_data(program_start)
        send_data_to_grit(df)

        logger.info("Pulling new backup from Grit now")
        pull_backup()
        logger.info("Backup pull complete")

    setup_logging()

    scheduler = BlockingScheduler()

    def sigint_handler(_signal, _frame):
        logging.getLogger("grit").info("Shutting down")
        scheduler.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGINT, sigint_handler)
    run()

    scheduler.add_job(run, "interval", minutes=30)
    scheduler.start()
