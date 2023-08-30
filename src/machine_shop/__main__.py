from datetime import datetime, timedelta
from pathlib import Path
from typing import cast

import polars as pl
from canvasapi import Canvas
from canvasapi.course import Course
from dotenv import load_dotenv

from .df_operations import upsert
from .env import get_quiz_ids, try_get_env

load_dotenv()


COURSE_ID = try_get_env("CANVAS_COURSE_ID")
QUIZ_IDS = get_quiz_ids()
API_URL = try_get_env("CANVAS_API_URL")
API_KEY = try_get_env("CANVAS_API_KEY")
DATABASE_PATH = Path(try_get_env("DATABASE_PATH"))


def get_quiz_results(
    course: Course,
    quiz_name: str,
    quiz_id: int,
    since_time: datetime,
) -> pl.LazyFrame:
    assignment = course.get_assignment(quiz_id)
    submissions = assignment.get_submissions(start_time=since_time)

    first_names: list[str] = []
    last_names: list[str] = []
    cwids: list[str] = []
    scores: list[float] = []
    emails: list[str] = []

    for sub in submissions:
        student = course.get_user(sub.user_id)
        last_name, first_name = cast(
            tuple[str, str], [n.strip() for n in student.sortable_name.split(",")]
        )
        cwid: str = student.sis_user_id
        if sub.grade is None:
            continue
        score = float(sub.grade.replace("%", ""))
        email: str = student.login_id

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
                "firstName": str,
                "lastName": str,
                "externalId": str,
                "email": str,
                quiz_name: pl.Float32,
            },
        )
        .filter(is_passing)
        .with_columns(is_passing)
    )


def get_database() -> pl.LazyFrame:
    return pl.read_excel(DATABASE_PATH).lazy()


def main():
    LAST_24_HOURS = datetime.now() - timedelta(hours=24)

    # database = get_database()
    # temporary, in theory grab the current list from grit?
    database = pl.LazyFrame(
        {
            "firstName": ["Not"],
            "lastName": ["Real"],
            "externalId": ["8675309"],
            "email": ["notreal@stevens.edu"],
            **{quiz_name: [True] for quiz_name in QUIZ_IDS.keys()},
        }
    )

    canvas = Canvas(API_URL, API_KEY)
    course = canvas.get_course(COURSE_ID)

    for quiz_name, quiz_id in QUIZ_IDS.items():
        results = get_quiz_results(
            course,
            quiz_name,
            quiz_id,
            LAST_24_HOURS,
        )

        database = upsert(
            database, results, ["externalId", "email", "firstName", "lastName"]
        )

    updated_db = database.with_columns(
        [
            pl.when(pl.col(c)).then(pl.lit("x")).otherwise(pl.lit(None)).alias(c)
            for c in QUIZ_IDS.keys()
        ]
    ).collect()

    updated_db.write_csv("grit_export.csv")


if __name__ == "__main__":
    main()
