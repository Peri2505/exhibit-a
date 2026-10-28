"""Happy-path tests. These must keep passing after any security fix."""
from conftest import login


def test_login_with_correct_password(client):
    resp = login(client, "alice", "alice-password")
    assert resp.status_code == 200
    assert resp.get_json()["username"] == "alice"


def test_login_with_wrong_password(client):
    assert login(client, "alice", "nope").status_code == 401


def test_alice_lists_her_notes(client, alice_token):
    resp = client.get("/api/notes", headers={"Authorization": f"Bearer {alice_token}"})
    assert resp.status_code == 200
    titles = [n["title"] for n in resp.get_json()["notes"]]
    assert titles == ["Groceries"]


def test_alice_reads_her_own_note(client, alice_token):
    resp = client.get("/api/notes/1", headers={"Authorization": f"Bearer {alice_token}"})
    assert resp.status_code == 200
    assert resp.get_json()["title"] == "Groceries"


def test_alice_creates_a_note(client, alice_token):
    headers = {"Authorization": f"Bearer {alice_token}"}
    resp = client.post("/api/notes", json={"title": "New", "body": "hi"}, headers=headers)
    assert resp.status_code == 201


def test_notes_require_login(client):
    assert client.get("/api/notes").status_code == 401
