import httpx

from .base import ProxyProvider
from .config import load_config

_LIST_URL = "https://proxy.webshare.io/api/v2/proxy/list/"


class WebshareProxyProvider(ProxyProvider):
    @classmethod
    def from_config(cls) -> "WebshareProxyProvider":
        cfg = load_config()
        return cls(api_key=cfg["webshare"]["api_key"])

    def __init__(self, api_key: str, page_size: int = 100):
        self._headers = {"Authorization": f"Token {api_key}"}
        self._page_size = page_size

    def list_all(self) -> list[str]:
        proxies: list[str] = []
        url: str | None = _LIST_URL
        params: dict = {"mode": "direct", "page_size": self._page_size}

        with httpx.Client() as client:
            while url:
                resp = client.get(url, params=params, headers=self._headers)
                resp.raise_for_status()
                data = resp.json()
                for p in data["results"]:
                    proxies.append(
                        f"http://{p['username']}:{p['password']}@{p['proxy_address']}:{p['port']}"
                    )
                url = data.get("next")
                params = {}

        return proxies
