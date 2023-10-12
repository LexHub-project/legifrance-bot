import json
from datetime import datetime
from time import time

import requests

URL_BASE = "https://api.piste.gouv.fr/dila/legifrance/lf-engine-app"


class LegifranceClient:
    _client_id: str
    _client_secret: str
    _token: str | None
    _token_expires_at: float

    def __init__(self, client_id: str, client_secret: str):
        self._client_id = client_id
        self._client_secret = client_secret
        self._token = None
        self._token_expires_at = time()

    def _get_token(self):
        res = requests.post(
            "https://oauth.piste.gouv.fr/api/oauth/token",
            data={
                "grant_type": "client_credentials",
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "scope": "openid",
            },
        )

        assert res.status_code == 200, res

        content = json.loads(res.content)
        self._token = content["access_token"]
        self._token_expires_at = time() + content["expires_in"] - 1
        print("@LegifranceClient: Authenticated")

    def _is_token_valid(self):
        return self._token is not None and self._token_expires_at > time()

    def _build_headers(self):
        if not self._is_token_valid():
            self._get_token()

        return {
            "Authorization": f"Bearer {self._token}",
            "accept": "application/json",
            "Content-Type": "application/json",
        }

    def get_codes_list(self):
        res = requests.post(
            URL_BASE + "/list/code",
            json.dumps(
                {
                    "pageSize": 100,
                    "pageNumber": 1,
                    "states": ["VIGUEUR"],  # "VIGUEUR", "ABROGE", "VIGEUR_DIIF"
                }
            ),
            headers=self._build_headers(),
        )

        assert res.status_code == 200, res

        return json.loads(res.content)["results"]

    def get_tm(self, cid: str):
        date_str = datetime.now().strftime("%Y-%m-%d")
        res = requests.post(
            URL_BASE + "/consult/legi/tableMatieres",
            json.dumps({"textId": cid, "nature": "CODE", "date": date_str}),
            headers=self._build_headers(),
        )

        assert res.status_code == 200, res

        return json.loads(res.content)

    def get_article(self, cid: str):
        res = requests.post(
            URL_BASE + "/consult/getArticleByCid",
            json.dumps({"cid": cid}),
            headers=self._build_headers(),
        )

        assert res.status_code == 200, res.content

        return json.loads(res.content)
