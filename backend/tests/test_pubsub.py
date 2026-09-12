"""In-process pub/sub bus — subscription lifecycle and channel isolation."""

import pytest

from app.core.pubsub import EventBus


@pytest.fixture
def bus():
    return EventBus()


class TestEventBus:
    @pytest.mark.asyncio
    async def test_subscriber_receives_published_message(self, bus):
        with bus.subscribe("ch1") as sub:
            bus.publish("ch1", {"id": "m1"})
            assert await sub.get(timeout=1.0) == {"id": "m1"}

    @pytest.mark.asyncio
    async def test_channels_are_isolated(self, bus):
        with bus.subscribe("ch1") as sub:
            bus.publish("ch2", {"id": "other"})
            assert await sub.get(timeout=0.05) is None

    @pytest.mark.asyncio
    async def test_timeout_returns_none_for_keepalive(self, bus):
        with bus.subscribe("ch1") as sub:
            assert await sub.get(timeout=0.05) is None

    @pytest.mark.asyncio
    async def test_no_delivery_after_unsubscribe(self, bus):
        with bus.subscribe("ch1") as sub:
            pass
        bus.publish("ch1", {"id": "late"})
        assert sub.queue.empty()

    @pytest.mark.asyncio
    async def test_fan_out_to_multiple_subscribers(self, bus):
        with bus.subscribe("ch1") as sub_a, bus.subscribe("ch1") as sub_b:
            bus.publish("ch1", {"id": "m1"})
            assert await sub_a.get(timeout=1.0) == {"id": "m1"}
            assert await sub_b.get(timeout=1.0) == {"id": "m1"}

    def test_publish_without_subscribers_does_not_raise(self, bus):
        bus.publish("empty", {"id": "void"})

    @pytest.mark.asyncio
    async def test_messages_delivered_in_order(self, bus):
        with bus.subscribe("ch1") as sub:
            for i in range(5):
                bus.publish("ch1", {"n": i})
            received = [await sub.get(timeout=1.0) for _ in range(5)]
            assert [m["n"] for m in received] == [0, 1, 2, 3, 4]
