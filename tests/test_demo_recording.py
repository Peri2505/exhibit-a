"""Guards the bundled demo recording: all five bugs must be proven and fixed."""
import json
import os

RUN = os.path.join(os.path.dirname(__file__), "..", "runs", "demo", "events.jsonl")


def _events():
    with open(RUN) as fh:
        return [json.loads(line) for line in fh if line.strip()]


def test_recording_exists_and_is_nonempty():
    assert os.path.exists(RUN)
    assert len(_events()) > 20


def test_all_five_findings_verified():
    verified = [e for e in _events() if e["type"] == "finding.verified"]
    assert len(verified) == 5


def test_nothing_reported_without_proof():
    # every verified finding carries a proof test path
    for e in _events():
        if e["type"] == "finding.verified":
            assert e["finding"]["test_path"]
            assert e["finding"]["diff"]
