# Task Tracker App

A fully-containerised task-management application built with a four-container architecture: a React SPA, a FastAPI backend, a PostgreSQL database, and an Nginx reverse proxy — all orchestrated with Docker Compose.

---

## Architecture Overview

```mermaid
graph TD
    Browser(["🌐 Browser\nhttp://localhost:80"])

    subgraph routine-net ["Docker Network — routine-net (bridge)"]
        Nginx["🔀 Nginx Reverse Proxy\nroutine-nginx : 80"]
        Frontend["⚛️ React SPA\nroutine-frontend : 80\n(Vite build → Nginx)"]
        Backend["🐍 FastAPI Backend\nroutine-backend : 5000\n(Python + Uvicorn)"]
        DB[("🐘 PostgreSQL\nroutine-db : 5432")]
    end

    Browser -- "HTTP :80 (only public port)" --> Nginx
    Nginx -- "/* (static files)" --> Frontend
    Nginx -- "/api/* (REST)" --> Backend
    Backend -- "psycopg2 / SQL" --> DB

    style routine-net fill:#f0f4ff,stroke:#4a6fa5,stroke-width:2px
    style Browser fill:#fff3cd,stroke:#856404
    style Nginx fill:#d1ecf1,stroke:#0c5460
    style Frontend fill:#d4edda,stroke:#155724
    style Backend fill:#d4edda,stroke:#155724
    style DB fill:#e2d9f3,stroke:#6f42c1
```

| Container           | Technology                  | Exposed internally | Host port |
|---------------------|-----------------------------|--------------------|-----------|
| `routine-nginx`     | Nginx (reverse proxy)       | 80                 | **80**    |
| `routine-frontend`  | React 18 + Vite → Nginx     | 80                 | —         |
| `routine-backend`   | Python 3 + FastAPI + Uvicorn| 5000               | —         |
| `routine-db`        | PostgreSQL 15               | 5432               | —         |

> Only `routine-nginx` publishes a port to the host. Every other service is reachable only within the shared `routine-net` bridge network.

---

## Docker Networking

### The `routine-net` Bridge Network

All four containers join a single user-defined bridge network called `routine-net` (declared in `docker-compose.yml`). Docker's embedded DNS resolver gives each container a DNS name that matches its **service name** — so containers call each other by name, not by IP:

| Caller            | Target DNS name | Port |
|-------------------|-----------------|------|
| `routine-nginx`   | `frontend`      | 80   |
| `routine-nginx`   | `backend`       | 5000 |
| `routine-backend` | `db`            | 5432 |

### Why a user-defined bridge (not the default)?

- **Automatic DNS resolution** — containers resolve each other by service name.
- **Isolation** — the network is invisible to containers outside this Compose project.
- **No unwanted exposure** — `backend`, `frontend`, and `db` have no `ports:` mapping; they cannot be reached from the host machine directly.

### Port exposure rules

```mermaid
graph LR
    subgraph Host ["🖥️ Host Machine"]
        HostPort[":80"]
    end

    subgraph routine-net ["Docker Network — routine-net"]
        Nginx["routine-nginx\n:80"]
        Frontend["routine-frontend\n:80 (internal)"]
        Backend["routine-backend\n:5000 (internal)"]
        DB["routine-db\n:5432 (internal)"]
    end

    HostPort -->|published| Nginx
    Nginx -->|"/* static"| Frontend
    Nginx -->|"/api/*"| Backend
    Backend -->|SQL| DB

    style Host fill:#fff9e6,stroke:#c8a400
    style routine-net fill:#f0f4ff,stroke:#4a6fa5,stroke-width:2px
```

> `backend`, `frontend`, and `db` use `expose:` (not `ports:`), so they are **unreachable from outside Docker** — traffic must flow through Nginx.

---

## Service-by-Service Breakdown

### Container Startup Sequence

```mermaid
sequenceDiagram
    participant DC as Docker Compose
    participant DB as routine-db (PostgreSQL)
    participant BE as routine-backend (FastAPI)
    participant FE as routine-frontend (React/Nginx)
    participant NX as routine-nginx (Proxy)

    DC->>DB: docker start
    DB->>DB: init.sql (first boot only)
    DB-->>DC: healthcheck pg_isready ✓

    DC->>BE: docker start (depends_on db: healthy)
    BE->>DB: init_db() — CREATE TABLE IF NOT EXISTS
    DB-->>BE: OK
    BE-->>DC: Uvicorn listening :5000

    DC->>FE: docker start
    FE-->>DC: Nginx serving /dist :80

    DC->>NX: docker start (depends_on frontend + backend)
    NX-->>DC: Nginx proxy listening :80
```

### 1. PostgreSQL (`db/`)

- **Image:** Custom image built from `db/Dockerfile` based on `postgres:15`.
- **Startup:** `db/init.sql` runs automatically on a **fresh** volume; it creates the `tasks` table. On subsequent starts the data directory already exists so the script is skipped — preventing data loss.
- **Persistence:** Data is stored in the named volume `postgres_data`. This volume survives `docker compose down` — use `docker compose down -v` to also delete the data.
- **Health check:** Docker waits for `pg_isready` to succeed before marking the service healthy. The backend's `depends_on: db: condition: service_healthy` ensures the API never starts before the database is ready to accept connections.
- **Credentials** (set as environment variables in `docker-compose.yml`):

  | Variable          | Value       |
  |-------------------|-------------|
  | `POSTGRES_DB`     | `tasksdb`   |
  | `POSTGRES_USER`   | `tasksuser` |
  | `POSTGRES_PASSWORD`| `taskspass`|

### 2. Backend (`backend/`)

- **Stack:** Python 3, FastAPI, Uvicorn, psycopg2.
- **Connection to DB:** Reads `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` from the environment. Docker Compose injects these so the backend dials `db:5432` (the service-name DNS entry on `routine-net`).
- **Startup retry:** `init_db()` retries the PostgreSQL connection for up to 30 seconds, sleeping 1 second between attempts. This is a safety net on top of the `service_healthy` condition.
- **Table initialisation:** On startup the backend runs `CREATE TABLE IF NOT EXISTS tasks (…)`, making it idempotent even if the DB already contains data.
- **No host port binding:** `expose: ["5000"]` makes the port reachable inside `routine-net` but not from the host.

### 3. Frontend (`frontend/`)

- **Stack:** React 18 + Vite 5 (development) → static files served by Nginx (production).
- **Multi-stage Docker build:**
  1. **Stage 1 (builder):** Node image runs `vite build`, producing optimised static assets in `/dist`.
  2. **Stage 2 (serve):** Nginx image copies only `/dist` — the final image contains no Node.js or source code.
- **API calls:** `src/api.js` sends all requests to the relative path `/api/tasks`. Because the URL is relative, it automatically goes to whatever origin served the page — i.e., `http://localhost/api/tasks` — which is caught by Nginx and proxied to the backend. **No hardcoded backend URL** exists in the frontend code.
- **No host port binding:** Only reachable via the proxy.

### 4. Nginx Reverse Proxy (`nginx/`)

- **Image:** Custom build from `nginx/Dockerfile`.
- **Single public entry point:** Binds `0.0.0.0:80` on the host and acts as the router for the entire application.
- **Routing logic** (`nginx/nginx.conf`):

  ```
  location /api  →  proxy_pass http://backend:5000
  location /     →  proxy_pass http://frontend:80
  ```

  Nginx forwards the original `Host`, `X-Real-IP`, and `X-Forwarded-For` headers so the backend can identify the true client IP if needed.
- **Upstream blocks:** Two named upstreams (`frontend` and `backend`) reference the Docker DNS names, keeping the config readable and easy to extend.

---

## Request / Response Flow

### Loading the page

```mermaid
sequenceDiagram
    participant B  as Browser
    participant NX as Nginx (proxy)
    participant FE as Frontend (React/Nginx)
    participant BE as Backend (FastAPI)
    participant DB as PostgreSQL

    B->>NX:  GET /
    NX->>FE: proxy_pass http://frontend:80
    FE-->>B: 200 index.html + JS/CSS bundle

    Note over B: React app boots, mounts App.jsx

    B->>NX:  GET /api/tasks
    NX->>BE: proxy_pass http://backend:5000
    BE->>DB: SELECT id,title,completed,description FROM tasks ORDER BY created_at
    DB-->>BE: rows[]
    BE-->>NX: 200 [{id,title,completed,description}, …]
    NX-->>B:  200 JSON array
    Note over B: React renders task list
```

### Creating a task

```mermaid
sequenceDiagram
    participant B  as Browser
    participant NX as Nginx (proxy)
    participant BE as Backend (FastAPI)
    participant DB as PostgreSQL

    Note over B: User submits AddTask form
    B->>NX:  POST /api/tasks  {title, description}
    NX->>BE: proxy_pass http://backend:5000
    BE->>BE: Pydantic TaskCreate validation
    BE->>DB: INSERT INTO tasks (id, title, completed, description)
    DB-->>BE: OK
    BE-->>NX: 201 {id, title, completed:false, description}
    NX-->>B:  201 new task JSON
    Note over B: React appends task to local state
```

### Toggling / editing a task

```mermaid
sequenceDiagram
    participant B  as Browser
    participant NX as Nginx (proxy)
    participant BE as Backend (FastAPI)
    participant DB as PostgreSQL

    Note over B: User clicks checkbox or edits title
    B->>NX:  PUT /api/tasks/{id}  {completed?, title?, description?}
    NX->>BE: proxy_pass http://backend:5000
    BE->>DB: SELECT existing row by id
    DB-->>BE: current row
    BE->>BE: merge patch fields with existing values
    BE->>DB: UPDATE tasks SET title=…,completed=…,description=… WHERE id=…
    DB-->>BE: OK
    BE-->>NX: 200 {id, title, completed, description}
    NX-->>B:  200 updated task JSON
    Note over B: React replaces task in local state
```

### Deleting a task

```mermaid
sequenceDiagram
    participant B  as Browser
    participant NX as Nginx (proxy)
    participant BE as Backend (FastAPI)
    participant DB as PostgreSQL

    Note over B: User clicks delete button
    B->>NX:  DELETE /api/tasks/{id}
    NX->>BE: proxy_pass http://backend:5000
    BE->>DB: DELETE FROM tasks WHERE id=…
    DB-->>BE: rowcount=1
    BE-->>NX: 204 No Content
    NX-->>B:  204
    Note over B: React removes task from local state
```

---

## REST API Reference

Base URL (via proxy): `http://localhost/api`

| Method   | Endpoint          | Request body                             | Success response          | Description          |
|----------|-------------------|------------------------------------------|---------------------------|----------------------|
| `GET`    | `/api/health`     | —                                        | `200 {"status":"ok"}`     | Health check         |
| `GET`    | `/api/tasks`      | —                                        | `200 [Task, …]`           | List all tasks       |
| `POST`   | `/api/tasks`      | `{"title":"…", "description":"…"}`       | `201 Task`                | Create a task        |
| `PUT`    | `/api/tasks/{id}` | `{"title"?, "completed"?, "description"?}` | `200 Task`              | Update a task        |
| `DELETE` | `/api/tasks/{id}` | —                                        | `204 No Content`          | Delete a task        |

### Task schema

```json
{
  "id":          "550e8400-e29b-41d4-a716-446655440000",
  "title":       "Buy groceries",
  "description": "Milk, eggs, bread",
  "completed":   false
}
```

### cURL examples

```bash
# Health check
curl http://localhost/api/health

# List all tasks
curl http://localhost/api/tasks

# Create a task
curl -X POST http://localhost/api/tasks \
     -H "Content-Type: application/json" \
     -d '{"title": "Buy groceries", "description": "Milk, eggs, bread"}'

# Mark a task complete  (replace <id> with the UUID from the create response)
curl -X PUT http://localhost/api/tasks/<id> \
     -H "Content-Type: application/json" \
     -d '{"completed": true}'

# Delete a task
curl -X DELETE http://localhost/api/tasks/<id>
```

---

## Database Schema

```sql
CREATE TABLE IF NOT EXISTS tasks (
    id          TEXT        PRIMARY KEY,          -- UUID v4 generated by FastAPI
    title       TEXT        NOT NULL,
    completed   BOOLEAN     NOT NULL DEFAULT FALSE,
    description TEXT        NOT NULL DEFAULT '',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW() -- used for ORDER BY in GET /api/tasks
);
```

Tasks are returned ordered by `created_at` so the list is stable and insertion-ordered.

---

## Quick Start

```bash
# Build all images and start all four containers
docker compose up --build

# Open in browser
http://localhost
```

```bash
# Stop all containers (data is preserved in the postgres_data volume)
docker compose down

# Stop and delete all data
docker compose down -v
```

---

## Project Structure

```
Task_Tracker_App/
├── docker-compose.yml        # Service orchestration & network/volume declarations
├── architecture.md           # Detailed architecture reference
├── README.md
├── db/
│   ├── Dockerfile            # Extends postgres:15
│   └── init.sql              # Creates tasks table on first boot
├── backend/
│   ├── app.py                # FastAPI app, routes, DB helpers, Pydantic models
│   ├── requirements.txt      # fastapi, uvicorn, psycopg2-binary
│   └── Dockerfile
├── frontend/
│   ├── Dockerfile            # Multi-stage: Vite build → Nginx serve
│   ├── index.html
│   ├── package.json
│   ├── vite.config.js
│   └── src/
│       ├── main.jsx          # React entry point
│       ├── App.jsx           # Root component — state & filter management
│       ├── App.css / index.css
│       ├── api.js            # Thin fetch wrapper for /api/tasks
│       └── components/
│           ├── AddTask.jsx   # New-task form
│           ├── TaskList.jsx  # Filtered list renderer
│           └── TaskItem.jsx  # Single task row (toggle, edit, delete)
└── nginx/
    ├── nginx.conf            # Upstream blocks + location routing rules
    └── Dockerfile
```

---

## Local Development (without Docker)

Run the backend and frontend in separate terminals. Vite's dev proxy rewrites `/api` requests to the local FastAPI server, mirroring the production Nginx routing.

**Database** — you need a local PostgreSQL instance:
```bash
createdb tasksdb
```

**Backend**
```bash
cd backend
pip install -r requirements.txt
POSTGRES_HOST=localhost POSTGRES_DB=tasksdb \
POSTGRES_USER=<user> POSTGRES_PASSWORD=<pass> \
uvicorn app:app --reload --port 5000
```

**Frontend**
```bash
cd frontend
npm install
npm run dev        # Vite dev server on http://localhost:5173
                   # vite.config.js proxies /api → http://localhost:5000
```
