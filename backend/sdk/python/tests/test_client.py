"""Tests for TrecoClient SDK — all methods, error handling, context manager."""
import pytest
import respx
from httpx import Response

from treco.client import TrecoClient

BASE_URL = "http://test-server:8001"
API_KEY = "treco_test_key_123"


def make_client() -> TrecoClient:
    return TrecoClient(api_key=API_KEY, base_url=BASE_URL)


@pytest.fixture
def client():
    return make_client()


class TestClientInit:
    def test_reads_env_vars(self, monkeypatch):
        monkeypatch.setenv("TRECO_API_KEY", "treco_env_key")
        monkeypatch.setenv("TRECO_URL", "http://env-server")
        c = TrecoClient()
        assert c._api_key == "treco_env_key"
        assert c._base_url == "http://env-server"

    def test_explicit_args_override_env(self, monkeypatch):
        monkeypatch.setenv("TRECO_API_KEY", "treco_env_key")
        c = TrecoClient(api_key="treco_explicit", base_url="http://explicit")
        assert c._api_key == "treco_explicit"

    def test_trailing_slash_stripped_from_base_url(self):
        c = TrecoClient(api_key="key", base_url="http://server/")
        assert not c._base_url.endswith("/")

    def test_missing_api_key_raises(self, monkeypatch):
        monkeypatch.delenv("TRECO_API_KEY", raising=False)
        with pytest.raises(KeyError):
            TrecoClient()


class TestEmitMethods:
    @pytest.mark.asyncio
    @respx.mock
    async def test_start(self, client):
        route = respx.post(f"{BASE_URL}/api/events/").mock(return_value=Response(200, json={"id": "e1"}))
        await client.start("ticket-1")
        assert route.called
        body = route.calls[0].request
        import json
        payload = json.loads(body.content)
        assert payload["event_type"] == "ticket_started"
        assert payload["ticket_id"] == "ticket-1"

    @pytest.mark.asyncio
    @respx.mock
    async def test_heartbeat(self, client):
        route = respx.post(f"{BASE_URL}/api/events/").mock(return_value=Response(200, json={"id": "e2"}))
        await client.heartbeat("ticket-2")
        assert route.called
        import json
        payload = json.loads(route.calls[0].request.content)
        assert payload["event_type"] == "heartbeat"

    @pytest.mark.asyncio
    @respx.mock
    async def test_log(self, client):
        route = respx.post(f"{BASE_URL}/api/events/").mock(return_value=Response(200, json={"id": "e3"}))
        await client.log("ticket-3", "hello world")
        import json
        payload = json.loads(route.calls[0].request.content)
        assert payload["event_type"] == "log"
        assert payload["payload"]["message"] == "hello world"

    @pytest.mark.asyncio
    @respx.mock
    async def test_done_with_tokens(self, client):
        route = respx.post(f"{BASE_URL}/api/events/").mock(return_value=Response(200, json={"id": "e4"}))
        await client.done("ticket-4", tokens_in=100, tokens_out=50)
        import json
        payload = json.loads(route.calls[0].request.content)
        assert payload["event_type"] == "done"
        assert payload["tokens_in"] == 100
        assert payload["tokens_out"] == 50

    @pytest.mark.asyncio
    @respx.mock
    async def test_error(self, client):
        route = respx.post(f"{BASE_URL}/api/events/").mock(return_value=Response(200, json={"id": "e5"}))
        await client.error("ticket-5", "something broke")
        import json
        payload = json.loads(route.calls[0].request.content)
        assert payload["event_type"] == "error"
        assert payload["payload"]["message"] == "something broke"

    @pytest.mark.asyncio
    @respx.mock
    async def test_check_criterion(self, client):
        route = respx.post(f"{BASE_URL}/api/events/").mock(return_value=Response(200, json={"id": "e6"}))
        await client.check("ticket-6", criterion_id="crit-abc", tokens_in=10, tokens_out=5)
        import json
        payload = json.loads(route.calls[0].request.content)
        assert payload["event_type"] == "criterion_checked"
        assert payload["criterion_id"] == "crit-abc"
        assert payload["tokens_in"] == 10

    @pytest.mark.asyncio
    @respx.mock
    async def test_fail_criterion(self, client):
        route = respx.post(f"{BASE_URL}/api/events/").mock(return_value=Response(200, json={"id": "e7"}))
        await client.fail_criterion("ticket-7", "crit-xyz", reason="not done")
        import json
        payload = json.loads(route.calls[0].request.content)
        assert payload["event_type"] == "criterion_failed"
        assert payload["criterion_id"] == "crit-xyz"
        assert payload["payload"]["reason"] == "not done"

    @pytest.mark.asyncio
    @respx.mock
    async def test_pr_opened(self, client):
        route = respx.post(f"{BASE_URL}/api/events/").mock(return_value=Response(200, json={"id": "e10"}))
        await client.pr_opened("ticket-10", url="https://github.com/org/repo/pull/42", pr_number=42)
        import json
        payload = json.loads(route.calls[0].request.content)
        assert payload["event_type"] == "pr_opened"
        assert payload["payload"]["url"] == "https://github.com/org/repo/pull/42"
        assert payload["payload"]["pr_number"] == 42

    @pytest.mark.asyncio
    @respx.mock
    async def test_pr_opened_without_number(self, client):
        route = respx.post(f"{BASE_URL}/api/events/").mock(return_value=Response(200, json={"id": "e11"}))
        await client.pr_opened("ticket-11", url="https://github.com/org/repo/pull/7")
        import json
        payload = json.loads(route.calls[0].request.content)
        assert payload["event_type"] == "pr_opened"
        assert payload["payload"]["url"] == "https://github.com/org/repo/pull/7"
        assert "pr_number" not in payload["payload"]

    @pytest.mark.asyncio
    @respx.mock
    async def test_x_agent_key_header_sent(self, client):
        route = respx.post(f"{BASE_URL}/api/events/").mock(return_value=Response(200, json={"id": "e8"}))
        await client.log("ticket-8", "check header")
        req = route.calls[0].request
        assert req.headers["x-agent-key"] == API_KEY

    @pytest.mark.asyncio
    @respx.mock
    async def test_http_error_propagates(self, client):
        respx.post(f"{BASE_URL}/api/events/").mock(return_value=Response(401))
        with pytest.raises(Exception):
            await client.log("ticket-err", "boom")

    @pytest.mark.asyncio
    @respx.mock
    async def test_log_with_extra_payload(self, client):
        route = respx.post(f"{BASE_URL}/api/events/").mock(return_value=Response(200, json={"id": "e9"}))
        await client.log("ticket-9", "msg", payload={"file": "foo.py"})
        import json
        payload = json.loads(route.calls[0].request.content)
        assert payload["payload"]["file"] == "foo.py"
        assert payload["payload"]["message"] == "msg"


class TestTrackContextManager:
    @pytest.mark.asyncio
    @respx.mock
    async def test_track_sends_start_and_done(self, client):
        calls: list[str] = []

        def capture(request, route):
            import json
            body = json.loads(request.content)
            calls.append(body["event_type"])
            return Response(200, json={"id": "x"})

        respx.post(f"{BASE_URL}/api/events/").mock(side_effect=capture)

        async with client.track("ticket-ctx"):
            pass

        assert "ticket_started" in calls
        assert "done" in calls

    @pytest.mark.asyncio
    @respx.mock
    async def test_track_sends_error_on_exception(self, client):
        calls: list[str] = []

        def capture(request, route):
            import json
            body = json.loads(request.content)
            calls.append(body["event_type"])
            return Response(200, json={"id": "x"})

        respx.post(f"{BASE_URL}/api/events/").mock(side_effect=capture)

        with pytest.raises(ValueError):
            async with client.track("ticket-err-ctx"):
                raise ValueError("oops")

        assert "error" in calls
        assert "done" not in calls


class TestClose:
    @pytest.mark.asyncio
    async def test_close_is_idempotent(self, client):
        await client.close()
        await client.close()  # should not raise


class TestHttpClientReuse:
    def test_constructor_creates_exactly_one_async_client(self, monkeypatch):
        import httpx
        created = []
        real_init = httpx.AsyncClient.__init__

        def counting_init(self, *args, **kwargs):
            created.append(self)
            real_init(self, *args, **kwargs)

        monkeypatch.setattr(httpx.AsyncClient, "__init__", counting_init)
        TrecoClient(api_key="k", base_url=BASE_URL)
        assert len(created) == 1

    @pytest.mark.asyncio
    @respx.mock
    async def test_same_client_instance_reused_across_calls(self, client):
        respx.post(f"{BASE_URL}/api/events/").mock(return_value=Response(200, json={"id": "x"}))
        before = client._http
        await client.log("t1", "one")
        await client.log("t1", "two")
        assert client._http is before
