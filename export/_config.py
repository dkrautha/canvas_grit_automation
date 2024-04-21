from pathlib import Path

from pydantic import BaseModel


class ExportConfig(BaseModel):
    backup_folder: Path


class MiscConfig(BaseModel):
    logging_config_file: Path


class Config(BaseModel):
    export: ExportConfig
    misc: MiscConfig
