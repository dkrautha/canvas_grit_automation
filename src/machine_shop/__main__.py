import io
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import cast

import polars as pl
import requests
from canvasapi import Canvas
from canvasapi.course import Course
from dotenv import load_dotenv

from .env import get_env_or_raise, get_quiz_ids

load_dotenv()

COURSE_ID = get_env_or_raise("CANVAS_COURSE_ID")
QUIZ_NAME_TO_IDS = get_quiz_ids()
QUIZ_IDS_TO_NAME = {v: k for k, v in QUIZ_NAME_TO_IDS.items()}
API_URL = get_env_or_raise("CANVAS_API_URL")
API_KEY = get_env_or_raise("CANVAS_API_KEY")
GRIT_URL = get_env_or_raise("GRIT_URL")
GRIT_API_KEY = get_env_or_raise("GRIT_API_KEY")
UPLOAD_TO_GRIT = get_env_or_raise("UPLOAD_TO_GRIT") == "true"
LOG_FOLDER = Path(get_env_or_raise("LOG_FOLDER"))
BACKUP_FOLDER = Path(get_env_or_raise("BACKUP_FOLDER"))

grit_logger = logging.getLogger("grit")
program_start = datetime.now(timezone.utc)


def setup_logging():
    grit_logger.setLevel(logging.DEBUG)
    timestamp = datetime.now().strftime("%Y_%m_%d")
    filepath = LOG_FOLDER / f"{timestamp}.txt"
    filepath.touch()
    file_handle = logging.FileHandler(filepath)
    file_handle.setLevel(logging.DEBUG)
    stderr_handler = logging.StreamHandler()
    grit_logger.addHandler(file_handle)
    grit_logger.addHandler(stderr_handler)


setup_logging()


def get_quiz_results(
    course: Course,
) -> pl.DataFrame:
    submissions = course.get_multiple_submissions(
        assignment_ids=QUIZ_NAME_TO_IDS.values(),
        submitted_since=program_start - timedelta(days=7),
        student_ids=["all"],
    )

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

        grit_logger.debug(
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

    gb = ["firstName", "lastName", "externalId", "email"]
    quiz_cols = pl.all().exclude(gb)
    df = df.group_by(gb).agg(quiz_cols.str.concat(""))
    print(df)
    df = df.with_columns(
        [
            pl.when(quiz_cols.str.lengths() == 0)
            .then(pl.lit(None))
            .otherwise(pl.lit("x"))
            .keep_name()
        ]
    )
    print(df)

    return df


def upsert_grit(file: io.BytesIO) -> requests.Response:
    session = requests.Session()
    request = session.prepare_request(
        requests.Request(
            method="POST",
            url=f"{GRIT_URL}/api/batch/user/upsert?"
            "processPermissionGroups=true&"
            "processRFiDCards=false&"
            "processDemographics=false&"
            "processAccessTimes=true&"
            "processMobileGritCard=false",
            headers={"x-auth-token": GRIT_API_KEY},
            files={"file": ("upload.csv", file.getvalue(), "text/csv")},
        )
    )
    response = session.send(request)
    return response


def main():
    start_time = datetime.now()
    grit_logger.info(f"Starting at {start_time}\n")

    canvas = Canvas(API_URL, API_KEY)
    course = canvas.get_course(COURSE_ID)

    df = get_quiz_results(course).with_columns(
        pl.lit("x").alias("at:Any Time"),
        active=pl.lit("x"),
    )

    # if no changes, then skip sending to grit
    if len(df) == 0:
        grit_logger.info("No changes")
        time_elapsed = datetime.now() - start_time
        grit_logger.info(f"Completed in {time_elapsed.total_seconds():.2f} seconds")
        return

    grit_csv = io.BytesIO()
    df.write_csv(grit_csv)

    grit_logger.info(f"CSV to send:\n{grit_csv.getvalue().decode('utf-8')}")

    if UPLOAD_TO_GRIT:
        response = upsert_grit(grit_csv)
        if not response.ok:
            grit_logger.warning("Request to Grit didn't return OK")
            grit_logger.warning(response.text)

    time_elapsed = datetime.now() - start_time
    grit_logger.info(f"Completed in {time_elapsed.total_seconds():.2f} seconds")

    grit_logger.info("Pulling new backup from Grit now")

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


if __name__ == "__main__":
    main()
