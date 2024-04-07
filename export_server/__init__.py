""""""

import io
from pathlib import Path

import polars as pl
import tomllib
from flask import Flask, Response, send_file
from pydantic import BaseModel


class Config(BaseModel):
    backup_folder: Path


with Path("configs/export_server_config.toml").open("rb") as f:
    config = Config.model_validate(tomllib.load(f))

app = Flask(__name__)


@app.route("/grit_export", methods=["GET"])
def grit_export() -> Response:
    most_recent_file = max(
        config.backup_folder.iterdir(),
        key=lambda x: x.stat().st_ctime,
        default=None,
    )

    if most_recent_file is None:
        return Response("No files found", 404)

    to_send = io.BytesIO()

    pl.read_csv(most_recent_file).select(
        pl.col(
            [
                "firstName",
                "lastName",
                "email",
                "pg:ATC User",
                "pg:ATC Supervisor",
                "pg:ATC Admin",
            ],
        ),
        pl.col("mobileGritCard").str.json_path_match(r"$.cardId").keep_name(),
    ).write_csv(to_send)

    to_send.seek(0)

    return send_file(
        to_send,
        mimetype="text/csv",
        as_attachment=True,
        download_name="grit_export.csv",
    )


def main() -> None:
    app.run(host="0.0.0.0", port=5000)


__all__ = []
