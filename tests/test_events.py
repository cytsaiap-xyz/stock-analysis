from agentcore.events import Event, EventBus


def test_emit_delivers_event_to_all_subscribers():
    bus = EventBus()
    seen_a, seen_b = [], []
    bus.subscribe(seen_a.append)
    bus.subscribe(seen_b.append)

    bus.emit(Event(type="message", agent="chair", data={"text": "hi"}))

    assert len(seen_a) == 1 and len(seen_b) == 1
    assert seen_a[0].type == "message"
    assert seen_a[0].agent == "chair"
    assert seen_a[0].data == {"text": "hi"}


def test_event_has_timestamp():
    e = Event(type="token", agent="x")
    assert isinstance(e.ts, float) and e.ts > 0
    assert e.data == {}
