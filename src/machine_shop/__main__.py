import io
import logging
from datetime import datetime, timedelta
from typing import cast

import polars as pl
import requests
from canvasapi import Canvas
from canvasapi.course import Course
from dotenv import load_dotenv

from .env import get_env_or_raise, get_quiz_ids

load_dotenv()
grit_logger = logging.getLogger("grit")
grit_logger.setLevel(logging.DEBUG)
file_handle = logging.FileHandler(get_env_or_raise("LOG_FILE"))
file_handle.setLevel(logging.DEBUG)
stderr_handler = logging.StreamHandler()
grit_logger.addHandler(file_handle)
grit_logger.addHandler(stderr_handler)

COURSE_ID = get_env_or_raise("CANVAS_COURSE_ID")
QUIZ_IDS = get_quiz_ids()
API_URL = get_env_or_raise("CANVAS_API_URL")
API_KEY = get_env_or_raise("CANVAS_API_KEY")
GRIT_URL = get_env_or_raise("GRIT_URL")
GRIT_API_KEY = get_env_or_raise("GRIT_API_KEY")
UPLOAD_TO_GRIT = get_env_or_raise("UPLOAD_TO_GRIT") == "true"


def get_quiz_results(
    course: Course,
    quiz_name: str,
    quiz_id: int,
    since_time: datetime | None = None,
) -> pl.LazyFrame:
    assignment = course.get_assignment(quiz_id)
    submissions = assignment.get_submissions(start_time=since_time)

    first_names: list[str] = []
    last_names: list[str] = []
    cwids: list[str] = []
    scores: list[float] = []
    emails: list[str] = []

    grit_logger.info("Getting submissions for %s", quiz_name)

    for sub in submissions:
        if sub.grade is None:
            continue
        score = float(sub.grade.replace("%", ""))
        student = course.get_user(sub.user_id)
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
            score,
            email,
        )

        first_names.append(first_name)
        last_names.append(last_name)
        cwids.append(cwid)
        scores.append(score)
        emails.append(email)

    is_passing = pl.col(quiz_name) >= 90
    return (
        pl.LazyFrame(
            {
                "firstName": first_names,
                "lastName": last_names,
                "externalId": cwids,
                "email": emails,
                quiz_name: scores,
            },
            {
                "firstName": pl.Utf8,
                "lastName": pl.Utf8,
                "externalId": pl.Utf8,
                "email": pl.Utf8,
                quiz_name: pl.Float32,
            },
        )
        .filter(is_passing)
        .with_columns(is_passing)
    )


def upsert_grit(file: io.BytesIO) -> requests.Response:
    session = requests.Session()
    request = session.prepare_request(
        requests.Request(
            method="POST",
            url=f"{GRIT_URL}/api/batch/user/upsert",
            headers={"x-auth-token": GRIT_API_KEY},
            files={"file": ("upload.csv", file.getvalue(), "text/csv")},
        )
    )
    response = session.send(request)
    return response


def main():
    start_time = datetime.now()
    grit_logger.info(f"Starting at {start_time}\n")
    last_24_hours = datetime.now() - timedelta(hours=24)

    canvas = Canvas(API_URL, API_KEY)
    course = canvas.get_course(COURSE_ID)

    for quiz_name, quiz_id in QUIZ_IDS.items():
        results = get_quiz_results(
            course,
            quiz_name,
            quiz_id,
            last_24_hours,
        ).with_columns(
            pl.when(pl.col(quiz_name))
            .then(pl.lit("x"))
            .otherwise(pl.lit(None))
            .alias(quiz_name),
            pl.lit("x").alias("at:Any Time"),
            active=pl.lit("x"),
        )

        results = results.collect()
        # if no changes for a quiz, then skip sending to grit
        if len(results) == 0:
            continue

        grit_csv = io.BytesIO()
        results.write_csv(grit_csv)

        grit_logger.info(f"CSV to send:\n{grit_csv.getvalue().decode('utf-8')}")

        if UPLOAD_TO_GRIT:
            response = upsert_grit(grit_csv)
            if not response.ok:
                grit_logger.warning("Request to Grit didn't return OK")
                grit_logger.warning(response.text)

    time_elapsed = datetime.now() - start_time
    grit_logger.info(f"Completed in {time_elapsed.total_seconds():.2f} seconds")


if __name__ == "__main__":
    main()
