import os
import time
import uuid

import psycopg2
import psycopg2.extras
from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

DB_CONFIG = {
    "host":     os.environ.get("POSTGRES_HOST", "localhost"),
    "port":     int(os.environ.get("POSTGRES_PORT", 5432)),
    "dbname":   os.environ.get("POSTGRES_DB", "tasksdb"),
    "user":     os.environ.get("POSTGRES_USER", "tasksuser"),
    "password": os.environ.get("POSTGRES_PASSWORD", "taskspass"),
}


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def get_db():
    return psycopg2.connect(**DB_CONFIG)


def init_db():
    """Create the tasks table if it doesn't exist.
    Retries for up to 30 seconds while PostgreSQL is starting up."""
    for attempt in range(30):
        try:
            conn = get_db()
            with conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """CREATE TABLE IF NOT EXISTS tasks (
                               id          TEXT        PRIMARY KEY,
                               title       TEXT        NOT NULL,
                               completed   BOOLEAN     NOT NULL DEFAULT FALSE,
                               description TEXT        NOT NULL DEFAULT '',
                               created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
                           )"""
                    )
            conn.close()
            return
        except psycopg2.OperationalError:
            if attempt == 29:
                raise
            time.sleep(1)


def row_to_dict(row):
    return {
        "id":          row["id"],
        "title":       row["title"],
        "completed":   row["completed"],
        "description": row["description"] or "",
    }


# Initialise on startup (idempotent – safe to call on every launch)
init_db()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@app.route("/api/tasks", methods=["GET"])
def get_tasks():
    conn = get_db()
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("SELECT id, title, completed, description FROM tasks ORDER BY created_at")
        rows = cur.fetchall()
    conn.close()
    return jsonify([row_to_dict(r) for r in rows])


@app.route("/api/tasks", methods=["POST"])
def create_task():
    data = request.get_json(silent=True)
    title = str(data.get("title", "")).strip() if data else ""
    if not title:
        return jsonify({"error": "title is required"}), 400

    description = str(data.get("description", "")).strip() if data else ""
    task_id = str(uuid.uuid4())
    conn = get_db()
    with conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO tasks (id, title, completed, description) VALUES (%s, %s, %s, %s)",
                (task_id, title, False, description),
            )
    conn.close()
    return jsonify({"id": task_id, "title": title, "completed": False, "description": description}), 201


@app.route("/api/tasks/<task_id>", methods=["PUT"])
def update_task(task_id):
    data = request.get_json(silent=True) or {}
    conn = get_db()
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("SELECT id, title, completed, description FROM tasks WHERE id = %s", (task_id,))
        row = cur.fetchone()
    if row is None:
        conn.close()
        return jsonify({"error": "task not found"}), 404

    title       = str(data.get("title", row["title"])).strip() or row["title"]
    completed   = bool(data.get("completed", row["completed"]))
    description = str(data.get("description", row["description"])).strip()

    with conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE tasks SET title = %s, completed = %s, description = %s WHERE id = %s",
                (title, completed, description, task_id),
            )
    conn.close()
    return jsonify({"id": task_id, "title": title, "completed": completed, "description": description})


@app.route("/api/tasks/<task_id>", methods=["DELETE"])
def delete_task(task_id):
    conn = get_db()
    with conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM tasks WHERE id = %s", (task_id,))
            deleted = cur.rowcount
    conn.close()
    if deleted == 0:
        return jsonify({"error": "task not found"}), 404
    return "", 204


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
