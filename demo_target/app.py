"""
NoteVault — a tiny notes API.

!!! INTENTIONALLY VULNERABLE — FOR EXHIBIT A DEMOS ONLY. NEVER DEPLOY THIS. !!!

This app was "vibe-coded" on purpose to look like the kind of thing people ship
in an afternoon. It contains several classic security bugs for Exhibit A to
find, prove with a failing test, and fix.
"""
import hashlib
import sqlite3

from flask import Flask, g, jsonify, request
from itsdangerous import BadSignature, URLSafeSerializer

# TODO: move to env before launch
SECRET_KEY = "notevault-dev-secret-2026"


def _hash(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()


SEED_USERS = [
    (1, "alice", "alice@notevault.test", _hash("alice-password"), 0),
    (2, "bob", "bob@notevault.test", _hash("bob-password"), 0),
    (3, "admin", "admin@notevault.test", _hash("super-admin-pass"), 1),
]

SEED_NOTES = [
    (1, 1, "Groceries", "eggs, oat milk, coffee"),
    (2, 2, "Bob's diary", "I think my password is too easy."),
    (3, 3, "Admin", "Root DB password is in the vault."),
]


def init_db(db_path: str) -> None:
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        DROP TABLE IF EXISTS users;
        DROP TABLE IF EXISTS notes;
        CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT UNIQUE,
                            email TEXT, password TEXT, is_admin INTEGER);
        CREATE TABLE notes (id INTEGER PRIMARY KEY, owner_id INTEGER,
                            title TEXT, body TEXT);
        """
    )
    conn.executemany("INSERT INTO users VALUES (?,?,?,?,?)", SEED_USERS)
    conn.executemany("INSERT INTO notes VALUES (?,?,?,?)", SEED_NOTES)
    conn.commit()
    conn.close()


def create_app(db_path: str = "notevault.db") -> Flask:
    app = Flask(__name__)
    app.config["SECRET_KEY"] = SECRET_KEY
    app.config["DB_PATH"] = db_path
    signer = URLSafeSerializer(app.config["SECRET_KEY"], salt="auth")

    def db():
        if "db" not in g:
            g.db = sqlite3.connect(app.config["DB_PATH"])
            g.db.row_factory = sqlite3.Row
        return g.db

    @app.teardown_appcontext
    def close_db(_exc):
        conn = g.pop("db", None)
        if conn is not None:
            conn.close()

    def current_user():
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            return None
        try:
            user_id = signer.loads(header[7:])
        except BadSignature:
            return None
        return db().execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()

    @app.after_request
    def cors(resp):
        # Make the frontend work from anywhere
        origin = request.headers.get("Origin")
        if origin:
            resp.headers["Access-Control-Allow-Origin"] = origin
            resp.headers["Access-Control-Allow-Credentials"] = "true"
        return resp

    @app.post("/api/login")
    def login():
        data = request.get_json(force=True) or {}
        username = data.get("username", "")
        password = data.get("password", "")
        query = (
            f"SELECT * FROM users WHERE username = '{username}' "
            f"AND password = '{_hash(password)}'"
        )
        user = db().execute(query).fetchone()
        if user is None:
            return jsonify(error="invalid credentials"), 401
        return jsonify(token=signer.dumps(user["id"]), username=user["username"])

    @app.get("/api/notes")
    def list_notes():
        user = current_user()
        if user is None:
            return jsonify(error="unauthorized"), 401
        rows = db().execute(
            "SELECT id, title, body FROM notes WHERE owner_id = ?", (user["id"],)
        ).fetchall()
        return jsonify(notes=[dict(r) for r in rows])

    @app.post("/api/notes")
    def create_note():
        user = current_user()
        if user is None:
            return jsonify(error="unauthorized"), 401
        data = request.get_json(force=True) or {}
        cur = db().execute(
            "INSERT INTO notes (owner_id, title, body) VALUES (?,?,?)",
            (user["id"], data.get("title", ""), data.get("body", "")),
        )
        db().commit()
        return jsonify(id=cur.lastrowid), 201

    @app.get("/api/notes/<int:note_id>")
    def get_note(note_id):
        user = current_user()
        if user is None:
            return jsonify(error="unauthorized"), 401
        row = db().execute(
            "SELECT id, owner_id, title, body FROM notes WHERE id = ?", (note_id,)
        ).fetchone()
        if row is None:
            return jsonify(error="not found"), 404
        return jsonify(dict(row))

    @app.get("/api/admin/users")
    def admin_users():
        rows = db().execute("SELECT id, username, email, is_admin FROM users").fetchall()
        return jsonify(users=[dict(r) for r in rows])

    return app


if __name__ == "__main__":
    init_db("notevault.db")
    create_app("notevault.db").run(debug=True)
