from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, send_file

from machine_shop.env import get_env_or_raise

app = Flask(__name__)


load_dotenv()
BACKUP_FOLDER = Path(get_env_or_raise("BACKUP_FOLDER"))


@app.route("/grit_export", methods=["GET"])
def grit_export():
    most_recent_file = max(
        BACKUP_FOLDER.iterdir(), key=lambda x: x.stat().st_ctime, default=None
    )
    if most_recent_file is None:
        return "No files found", 404

    return send_file(
        most_recent_file,
        mimetype="text/csv",
        as_attachment=True,
        download_name="grit_export.csv",
    )
