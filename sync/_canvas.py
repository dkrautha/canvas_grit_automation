from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Self, cast

import polars as pl
from bidict import bidict
from canvasapi import Canvas
from canvasapi.submission import Submission

if TYPE_CHECKING:
    from canvasapi.course import Course
    from canvasapi.group import Group

    from ._config import CanvasConfig

logger = logging.getLogger("sync")


class CanvasSync:
    _canvas: Canvas
    _course: Course
    _grit_permission_quizzes: bidict[str, int]
    _group_tracking_quizzes: bidict[str, int]
    _quiz_id_to_group_id: dict[int, Group]
    _initialize_time = datetime.now(timezone.utc)

    def __init__(
        self: Self,
        config: CanvasConfig,
    ) -> None:
        self._canvas = Canvas(config.api_url, config.api_key)
        self._course = self._canvas.get_course(config.course_id)
        self._grit_permission_quizzes = bidict(config.grit_permission_quizzes)
        self._group_tracking_quizzes = bidict(config.group_tracking_quizzes)
        self._quiz_id_to_group_id = {
            k: self._canvas.get_group(v) for k, v in config.quiz_id_to_group_id.items()
        }

    def get_passing_results(self: Self, passing_score: int = 90) -> pl.DataFrame:
        submissions = self._course.get_multiple_submissions(
            assignment_ids=self._grit_permission_quizzes.values()
            | self._group_tracking_quizzes.values(),
            submitted_since=self._initialize_time - timedelta(days=7),
            student_ids=["all"],
        )

        logger.info("Received submissions from Canvas")

        schema = {
            "firstName": pl.Utf8,
            "lastName": pl.Utf8,
            "externalId": pl.Utf8,
            "email": pl.Utf8,
            **{quiz_name: pl.Utf8 for quiz_name in self._grit_permission_quizzes},
        }

        passing = pl.DataFrame(schema=schema)

        for sub in submissions:
            sub = cast(Submission, sub)
            if sub.grade is None:
                continue

            grade = float(cast(str, sub.grade).replace("%", ""))
            if grade < passing_score:
                continue

            quiz_id = sub.assignment_id
            quiz_name = self._grit_permission_quizzes.inverse.get(
                quiz_id,
            ) or self._group_tracking_quizzes.inverse.get(
                quiz_id,
            )
            user_id = sub.user_id
            student = self._course.get_user(user_id)

            last_name, first_name = cast(
                tuple[str, str],
                [n.strip() for n in student.sortable_name.split(",")],
            )

            if first_name == "Test" and last_name == "Student":
                continue

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

            if quiz_id in self._grit_permission_quizzes.inverse:
                row = pl.DataFrame(
                    {
                        "firstName": first_name,
                        "lastName": last_name,
                        "externalId": cwid,
                        "email": email,
                        **{
                            q: "x" if q == quiz_name else ""
                            for q in self._grit_permission_quizzes
                        },
                    },
                )
                passing = passing.vstack(row)

            # to be enabled once proper groups have been created
            # if (group := self._quiz_id_to_group_id.get(quiz_id)) is not None:
            #     logger.debug(
            #         "Adding %s %s to group %s",
            #         first_name,
            #         last_name,
            #         group.name,
            #     )
            #     group.create_membership(student)

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
