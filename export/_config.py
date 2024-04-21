from pathlib import Path

from pydantic import BaseModel


class Config(BaseModel):
    backup_folder: Path
