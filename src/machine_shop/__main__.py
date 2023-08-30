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
    grades = course.get_grade_change_events(
        assignment_id=quiz_id,
        start_time=since_time,
    )

    first_names: list[str] = []
    last_names: list[str] = []
    cwids: list[str] = []
    scores: list[float] = []
    emails: list[str] = []

    for grade in grades:
        student = course.get_user(grade.links["student"])
        last_name, first_name = cast(
            tuple[str, str], [n.strip() for n in student.sortable_name.split(",")]
        )
        cwid: str = student.sis_user_id
        score: float = float(grade.grade_after.replace("%", ""))
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
                "first_name": first_names,
                "last_name": last_names,
                "cwid": cwids,
                "email": emails,
                quiz_name: scores,
            }
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
            "first_name": ["Not"],
            "last_name": ["Real"],
            "cwid": ["8675309"],
            "email": ["notreal@stevens.edu"],
            "drill_press": [True],
            "3d_printers": [False],
            "band_saw": [False],
            "atc": [True],
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
            database, results, ["cwid", "email", "first_name", "last_name"]
        )

    def bool_transform(x: bool) -> str | None:
        return "x" if x else None

    updated_db = database.with_columns(
        # this can be replaced with a regex once the correct column names
        # are in (I think they all start with "pb:" or something like that)
        pl.col(pl.Boolean).apply(bool_transform)
    ).collect()

    print(updated_db)
    # updated_db.write_csv("grit_export.csv")


if __name__ == "__main__":
    main()
