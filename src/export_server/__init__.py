import io
from datetime import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv
from flask import Flask, send_file

from machine_shop.env import get_env_or_raise

app = Flask(__name__)


load_dotenv()
GRIT_URL = get_env_or_raise("GRIT_URL")
GRIT_API_KEY = get_env_or_raise("GRIT_API_KEY")


@app.route("/grit_export", methods=["GET"])
def grit_export():
    session = requests.Session()
    request = session.prepare_request(
        requests.Request(
            method="GET",
            url=f"{GRIT_URL}/api/batch/user/export",
            headers={"x-auth-token": GRIT_API_KEY},
        )
    )
    response = session.send(request)
    file = io.BytesIO(response.content)
    timestamp = datetime.now().strftime("%Y_%m_%d_%H_%M")
    file_name = Path(f"grit_export_{timestamp}.xlsx")
    file_name.write_bytes(file.getvalue())
    return send_file(file, mimetype="application/vnd.ms-excel")
