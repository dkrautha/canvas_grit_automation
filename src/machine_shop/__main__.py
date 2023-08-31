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
    since_time: datetime | None = None,
) -> pl.LazyFrame:
    assignment = course.get_assignment(quiz_id)
    submissions = assignment.get_submissions(start_time=since_time)

    first_names: list[str] = []
    last_names: list[str] = []
    cwids: list[str] = []
    scores: list[float] = []
    emails: list[str] = []
    enrolled_year: list[datetime] = []

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
        enrolled: datetime = student.created_at_date

        first_names.append(first_name)
        last_names.append(last_name)
        cwids.append(cwid)
        scores.append(score)
        emails.append(email)
        enrolled_year.append(enrolled)

    is_passing = pl.col(quiz_name) >= 90
    return (
        pl.LazyFrame(
            {
                "firstName": first_names,
                "lastName": last_names,
                "externalId": cwids,
                "email": emails,
                "enrollment_date": enrolled_year,
                quiz_name: scores,
            },
            {
                "firstName": pl.Utf8,
                "lastName": pl.Utf8,
                "externalId": pl.Utf8,
                "email": pl.Utf8,
                "enrollment_date": pl.Datetime,
                quiz_name: pl.Float32,
            },
        )
        .filter(is_passing)
        .with_columns(is_passing)
    )


def get_database() -> pl.LazyFrame:
    return pl.scan_csv(DATABASE_PATH, dtypes={"externalId": pl.Utf8})


def main():
    LAST_24_HOURS = datetime.now() - timedelta(hours=24)

    database = get_database()
    updated_db = database

    canvas = Canvas(API_URL, API_KEY)
    course = canvas.get_course(COURSE_ID)

    for quiz_name, quiz_id in QUIZ_IDS.items():
        results = get_quiz_results(
            course,
            quiz_name,
            quiz_id,
            None,  # Change to LAST_24_HOURS in future
        )

        updated_db = upsert(
            updated_db, results, ["externalId", "email", "firstName", "lastName"]
        )

    database = database.collect()
    database.write_csv(
        f"{DATABASE_PATH.with_suffix('')}_{datetime.now().strftime('%Y_%m_%d_%H_%M_%S')}{DATABASE_PATH.suffix}"
    )

    updated_db = updated_db.collect()
    updated_db.write_csv(DATABASE_PATH)

    give_to_grit = updated_db.with_columns(
        [
            pl.when(pl.col(c)).then(pl.lit("x")).otherwise(pl.lit(None)).alias(c)
            for c in QUIZ_IDS.keys()
        ]
    ).drop("enrollment_date")
    give_to_grit.write_csv("give_to_grit.csv")


if __name__ == "__main__":
    import cProfile

    cProfile.run("main()", sort="tottime")
