import os
import time
import uuid
from contextlib import asynccontextmanager

import psycopg2
import psycopg2.extras
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

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


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class TaskCreate(BaseModel):
    title: str
    description: str = ""


class TaskUpdate(BaseModel):
    title: str | None = None
    completed: bool | None = None
    description: str | None = None


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/tasks")
def get_tasks():
    conn = get_db()
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("SELECT id, title, completed, description FROM tasks ORDER BY created_at")
        rows = cur.fetchall()
    conn.close()
    return [row_to_dict(r) for r in rows]


@app.post("/api/tasks", status_code=201)
def create_task(body: TaskCreate):
    title = body.title.strip()
    if not title:
        raise HTTPException(status_code=400, detail="title is required")

    description = body.description.strip()
    task_id = str(uuid.uuid4())
    conn = get_db()
    with conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO tasks (id, title, completed, description) VALUES (%s, %s, %s, %s)",
                (task_id, title, False, description),
            )
    conn.close()
    return {"id": task_id, "title": title, "completed": False, "description": description}


@app.put("/api/tasks/{task_id}")
def update_task(task_id: str, body: TaskUpdate):
    conn = get_db()
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("SELECT id, title, completed, description FROM tasks WHERE id = %s", (task_id,))
        row = cur.fetchone()
    if row is None:
        conn.close()
        raise HTTPException(status_code=404, detail="task not found")

    title       = (body.title.strip() if body.title is not None else None) or row["title"]
    completed   = body.completed if body.completed is not None else row["completed"]
    description = body.description.strip() if body.description is not None else row["description"]

    with conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE tasks SET title = %s, completed = %s, description = %s WHERE id = %s",
                (title, completed, description, task_id),
            )
    conn.close()
    return {"id": task_id, "title": title, "completed": completed, "description": description}


@app.delete("/api/tasks/{task_id}", status_code=204)
def delete_task(task_id: str):
    conn = get_db()
    with conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM tasks WHERE id = %s", (task_id,))
            deleted = cur.rowcount
    conn.close()
    if deleted == 0:
        raise HTTPException(status_code=404, detail="task not found")
