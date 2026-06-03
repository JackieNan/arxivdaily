from dataclasses import dataclass
import time

import httpx


@dataclass(frozen=True)
class FetchResponse:
    url: str
    status_code: int
    text: str


class ArxivHttpClient:
    def __init__(
        self,
        *,
        timeout_seconds: float = 20.0,
        max_attempts: int = 3,
        retry_sleep_seconds: float = 1.0,
        transport: httpx.BaseTransport | None = None,
    ):
        self.max_attempts = max_attempts
        self.retry_sleep_seconds = retry_sleep_seconds
        self.client = httpx.Client(
            timeout=timeout_seconds,
            transport=transport,
            headers={"User-Agent": "arxiv-local-daily/0.1"},
            follow_redirects=True,
        )

    def fetch_text(self, url: str) -> FetchResponse:
        last_response: httpx.Response | None = None
        for attempt in range(1, self.max_attempts + 1):
            response = self.client.get(url)
            last_response = response
            if response.status_code < 500:
                return FetchResponse(
                    url=str(response.url),
                    status_code=response.status_code,
                    text=response.text,
                )
            if attempt < self.max_attempts:
                time.sleep(self.retry_sleep_seconds)
        assert last_response is not None
        return FetchResponse(
            url=str(last_response.url),
            status_code=last_response.status_code,
            text=last_response.text,
        )

    def close(self) -> None:
        self.client.close()
