""""""

import io
import json
import logging
import logging.config
from pathlib import Path

import polars as pl
import tomllib  # TODO: use std library toml
from flask import Flask, Response, send_file

from ._config import Config

with Path("configs/export_config.toml").open("rb") as f:
    export_config = Config.model_validate(tomllib.load(f))


def setup_logging() -> None:
    config_file = Path("configs/export_logging_config.json")
    with config_file.open() as f:
        config = json.load(f)
    logging.config.dictConfig(config)


app = Flask(__name__)


@app.route("/grit_export", methods=["GET"])
def grit_export() -> Response:
    most_recent_file = max(
        export_config.export.backup_folder.iterdir(),
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
    setup_logging()
    app.run(host="0.0.0.0", port=5000)


__all__ = []
