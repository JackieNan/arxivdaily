import httpx

from arxiv_local_daily.crawler.http import ArxivHttpClient


def test_fetch_text_retries_transient_server_errors():
    attempts: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(1)
        if len(attempts) == 1:
            return httpx.Response(503, text="temporary")
        return httpx.Response(200, text="ok")

    client = ArxivHttpClient(
        transport=httpx.MockTransport(handler),
        retry_sleep_seconds=0,
    )

    response = client.fetch_text("https://arxiv.org/list/cs.AI/new")

    assert response.status_code == 200
    assert response.text == "ok"
    assert len(attempts) == 2


def test_fetch_text_sends_polite_user_agent():
    seen_user_agent: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_user_agent.append(request.headers["User-Agent"])
        return httpx.Response(200, text="ok")

    client = ArxivHttpClient(
        transport=httpx.MockTransport(handler),
        retry_sleep_seconds=0,
    )

    client.fetch_text("https://arxiv.org/list/cs.AI/new")

    assert seen_user_agent == ["arxiv-local-daily/0.1"]
