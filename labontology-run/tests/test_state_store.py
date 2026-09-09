from runtime.models import MissionState
from runtime.state_store import StateStore


def test_state_store_persists_state_and_events(tmp_path):
    store = StateStore(tmp_path, "mission:test")
    state = MissionState(mission_id="mission:test")
    store.save(state)
    store.event("mission_created", {"mode": "agent"})

    loaded = store.load()

    assert loaded.mission_id == "mission:test"
    assert loaded.mode == "agent"
    events = (store.run_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()
    assert '"event": "mission_created"' in events[0]
