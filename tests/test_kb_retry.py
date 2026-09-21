from soc_kb.confluence import ConfluenceClient


class Response:
    def __init__(self, status, payload=None, headers=None):
        self.status_code = status
        self._payload = payload or {}
        self.headers = headers or {}
        self.text = "error"

    def json(self):
        return self._payload


class Session:
    def __init__(self, responses):
        self.responses = list(responses)
        self.auth = None
        self.headers = {}
        self.calls = 0

    def request(self, *args, **kwargs):
        self.calls += 1
        return self.responses.pop(0)


def test_retries_rate_limit_and_honors_retry_after():
    session = Session([Response(429, headers={"Retry-After": "1"}), Response(200, {"results": []})])
    sleeps = []
    client = ConfluenceClient("https://example.atlassian.net", "a", "b", session=session, sleeper=sleeps.append)
    response = client.request("GET", "/pages")
    assert response.status_code == 200
    assert session.calls == 2
    assert sleeps == [1.0]
