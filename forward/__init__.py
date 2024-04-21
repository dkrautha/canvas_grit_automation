""""""

import json
import logging
import logging.config
from pathlib import Path

import requests
import tomllib
from flask import Flask, Response, request

from ._config import Config

with Path("configs/forward_config.toml").open("rb") as f:
    forward_config = Config.model_validate(tomllib.load(f))


def setup_logging() -> None:
    config_file = Path("configs/forward_logging_config.json")
    with config_file.open() as f:
        config = json.load(f)
    logging.config.dictConfig(config)


app = Flask(__name__)


# https://stackoverflow.com/questions/6656363/proxying-to-another-web-service-with-flask
@app.route("/", defaults={"path": ""}, methods=["GET", "POST"])
@app.route("/<path>", methods=["GET", "POST"])
def redirect_to_grit(path) -> Response:
    res = requests.request(
        method=request.method,
        url=request.url.replace(request.host_url, f"{forward_config.url}/"),
        headers={
            k: v for k, v in request.headers if k.lower() != "host"
        },  # exclude 'host' header
        data=request.get_data(),
        cookies=request.cookies,
        allow_redirects=False,
    )

    excluded_headers = [
        "content-encoding",
        "content-length",
        "transfer-encoding",
        "connection",
    ]
    headers = [
        (k, v) for k, v in res.raw.headers.items() if k.lower() not in excluded_headers
    ]

    return Response(res)


def main() -> None:
    setup_logging()
    app.run(host="0.0.0.0", port=5000)


__all__ = []
