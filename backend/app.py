import os
import sqlite3
import uuid

from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

DB_PATH = os.environ.get("DB_PATH", "tasks.db")


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def init_db():
    db_dir = os.path.dirname(DB_PATH)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS tasks (
               id          TEXT PRIMARY KEY,
               title       TEXT NOT NULL,
               completed   INTEGER NOT NULL DEFAULT 0,
               description TEXT    NOT NULL DEFAULT ''
           )"""
    )
    # Migrate existing databases that were created without the description column
    try:
        conn.execute("ALTER TABLE tasks ADD COLUMN description TEXT NOT NULL DEFAULT ''")
    except sqlite3.OperationalError:
        pass  # column already exists
    conn.commit()
    conn.close()


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def row_to_dict(row):
    return {
        "id": row["id"],
        "title": row["title"],
        "completed": bool(row["completed"]),
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
    rows = conn.execute("SELECT * FROM tasks ORDER BY rowid").fetchall()
    conn.close()
    return jsonify([row_to_dict(r) for r in rows])


@app.route("/api/tasks", methods=["POST"])
def create_task():
    data = request.get_json(silent=True)
    title = str(data.get("title", "")).strip() if data else ""
    if not title:
        return jsonify({"error": "title is required"}), 400

    description = str(data.get("description", "")).strip() if data else ""
    task = {"id": str(uuid.uuid4()), "title": title, "completed": False, "description": description}
    conn = get_db()
    conn.execute(
        "INSERT INTO tasks (id, title, completed, description) VALUES (?, ?, ?, ?)",
        (task["id"], task["title"], 0, task["description"]),
    )
    conn.commit()
    conn.close()
    return jsonify(task), 201


@app.route("/api/tasks/<task_id>", methods=["PUT"])
def update_task(task_id):
    data = request.get_json(silent=True) or {}
    conn = get_db()
    row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if row is None:
        conn.close()
        return jsonify({"error": "task not found"}), 404

    title = str(data.get("title", row["title"])).strip() or row["title"]
    completed = bool(data.get("completed", row["completed"]))
    description = str(data.get("description", row["description"])).strip()

    conn.execute(
        "UPDATE tasks SET title = ?, completed = ?, description = ? WHERE id = ?",
        (title, int(completed), description, task_id),
    )
    conn.commit()
    conn.close()
    return jsonify({"id": task_id, "title": title, "completed": completed, "description": description})


@app.route("/api/tasks/<task_id>", methods=["DELETE"])
def delete_task(task_id):
    conn = get_db()
    result = conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    conn.commit()
    conn.close()
    if result.rowcount == 0:
        return jsonify({"error": "task not found"}), 404
    return "", 204


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
