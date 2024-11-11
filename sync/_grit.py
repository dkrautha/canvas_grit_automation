import io
import logging
from typing import Self

import polars as pl
import requests

logger = logging.getLogger("grit")


class Grit:
    _session: requests.Session
    _api_key: str
    _url: str

    def __init__(self: Self, url: str, api_key: str) -> None:
        self._session = requests.Session()
        self._api_key = api_key
        self._url = url

    def upsert(self: Self, df: pl.DataFrame) -> requests.Response:
        # TODO(David): might be able to get away with just using write_csv returning a
        # string, but unsure if requests will be happy with that
        # leaving as is for now to not break anything
        csv = io.BytesIO()
        df = df.unique(subset=["externalId"], keep="last")
        df.write_csv(csv)

        request = self._session.prepare_request(
            requests.Request(
                method="POST",
                url=f"{self._url}/api/batch/user/upsert",
                # url=f"{GRIT_URL}/api/batch/user/upsert?",
                # "processPermissionGroups=true&"
                # "processRFiDCards=false&"
                # "processDemographics=false&"
                # "processAccessTimes=true&"
                # "processMobileGritCard=false",
                headers={"x-auth-token": self._api_key},
                files={"file": ("upload.csv", csv.getvalue(), "text/csv")},
            ),
        )

        return self._session.send(request, timeout=20)

    def get_backup(self: Self) -> pl.DataFrame:
        request = self._session.prepare_request(
            requests.Request(
                method="GET",
                url=f"{self._url}/api/batch/user/export",
                headers={"x-auth-token": self._api_key},
            ),
        )

        response = self._session.send(request, timeout=20)
        content = io.BytesIO(response.content)
        return pl.read_excel(content)


__all__ = ["Grit"]
