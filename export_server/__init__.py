from pathlib import Path

import polars as pl
from flask import Flask, send_file
from sync.env import get_env_or_raise

app = Flask(__name__)


BACKUP_FOLDER = Path(get_env_or_raise("BACKUP_FOLDER"))


@app.route("/grit_export", methods=["GET"])
def grit_export():
    most_recent_file = max(
        BACKUP_FOLDER.iterdir(), key=lambda x: x.stat().st_ctime, default=None
    )
    if most_recent_file is None:
        return "No files found", 404

    data = pl.read_csv(most_recent_file).with_columns(
        pl.col(
            [
                "firstName",
                "lastName",
                "email" "pg:ATC User",
                "pg:ATC Supervisor",
                "pg:ATC Admin",
            ]
        )
    )

    return send_file(
        most_recent_file,
        mimetype="text/csv",
        as_attachment=True,
        download_name="grit_export.csv",
    )


def main():
    app.run(host="0.0.0.0", port=5000)
