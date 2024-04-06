import logging
from datetime import datetime, timedelta, timezone
from typing import Self, cast

import polars as pl
from bidict import bidict
from canvasapi import Canvas
from canvasapi.course import Course

logger = logging.getLogger("sync")


class CanvasSync:
    _canvas: Canvas
    _course: Course
    _quiz_name_to_id_map: bidict[str, int]
    _initialize_time = datetime.now(timezone.utc)

    def __init__(
        self: Self,
        url: str,
        api_key: str,
        course_id: int,
        quiz_name_to_id_map: bidict[str, int],
    ) -> None:
        self._canvas = Canvas(url, api_key)
        self._course = self._canvas.get_course(course_id)
        self._quiz_name_to_id_map = quiz_name_to_id_map

    def get_passing_results(self: Self, passing_score: int = 90) -> pl.DataFrame:
        submissions = self._course.get_multiple_submissions(
            assignment_ids=self._quiz_name_to_id_map.values(),
            submitted_since=self._initialize_time - timedelta(days=7),
            student_ids=["all"],
        )

        logger.info("Received submissions from Canvas")

        schema = {
            "firstName": pl.Utf8,
            "lastName": pl.Utf8,
            "externalId": pl.Utf8,
            "email": pl.Utf8,
            **{quiz_name: pl.Utf8 for quiz_name in self._quiz_name_to_id_map},
        }

        passing = pl.DataFrame(schema=schema)

        for sub in submissions:
            if sub.grade is None:
                continue

            grade = float(cast(str, sub.grade).replace("%", ""))
            if grade < passing_score:
                continue

            quiz_name = self._quiz_name_to_id_map.inverse[sub.assignment_id]
            user_id = sub.user_id
            student = self._course.get_user(user_id)

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
                    **{
                        q: "x" if q == quiz_name else ""
                        for q in self._quiz_name_to_id_map
                    },
                },
            )
            passing = passing.vstack(row)

        logger.info("Processed submissions from Canvas")

        # TODO(David): name this better
        gb = ["firstName", "lastName", "externalId", "email"]
        quiz_cols = pl.all().exclude(gb)
        grouped_by = passing.group_by(gb).agg(quiz_cols.str.concat(""))
        mark_xs = grouped_by.with_columns(
            [
                pl.when(quiz_cols.str.len_bytes() == 0)
                .then(pl.lit(None))
                .otherwise(pl.lit("x"))
                .name.keep(),
            ],
        )

        return mark_xs.with_columns(
            pl.lit("x").alias("at:Any Time"),
            active=pl.lit("x"),
        )


__all__ = ["CanvasSync"]
