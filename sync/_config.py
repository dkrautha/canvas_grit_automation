from __future__ import annotations

from pathlib import Path  # noqa: TCH003

from pydantic import BaseModel


class CanvasConfig(BaseModel):
    api_url: str
    api_key: str
    course_id: int
    quizzes: dict[str, int]


class GritConfig(BaseModel):
    api_url: str
    api_key: str
    perform_upload: bool


class MiscConfig(BaseModel):
    backup_folder: Path


class Config(BaseModel):
    canvas: CanvasConfig
    grit: GritConfig
    misc: MiscConfig
