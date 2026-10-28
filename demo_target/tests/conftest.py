import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app, init_db  # noqa: E402


@pytest.fixture
def app(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    application = create_app(db_path)
    application.config["TESTING"] = True
    return application


@pytest.fixture
def client(app):
    return app.test_client()


def login(client, username, password):
    resp = client.post("/api/login", json={"username": username, "password": password})
    return resp


@pytest.fixture
def alice_token(client):
    return login(client, "alice", "alice-password").get_json()["token"]


@pytest.fixture
def bob_token(client):
    return login(client, "bob", "bob-password").get_json()["token"]
