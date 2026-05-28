# Docker Networking — Task Tracker App

This document explains every networking decision made in this project: how containers find each other, which ports are exposed, how traffic flows, and why each choice was made.

---

## 1. High-Level Overview

```mermaid
graph TD
    Browser["🌐 Browser\n(localhost:80)"]

    subgraph Host["Host Machine"]
        Port80["Host port 80"]
    end

    subgraph routine-net["Docker Bridge Network — routine-net"]
        Nginx["nginx\nroutine-nginx\n:80"]
        Frontend["frontend\nroutine-frontend\n:80  (internal only)"]
        Backend["backend\nroutine-backend\n:5000  (internal only)"]
        DB["db\nroutine-db\n:5432  (internal only)"]
    end

    Volume[("postgres_data\nNamed Volume")]

    Browser -->|HTTP request| Port80
    Port80  -->|mapped to| Nginx
    Nginx   -->|/api/*  →  proxy_pass| Backend
    Nginx   -->|/*      →  proxy_pass| Frontend
    Backend -->|SQL over TCP :5432| DB
    DB      --- Volume
```

**Key principle:** Only Nginx publishes a port to the host (`80:80`). Every other container lives exclusively inside the private `routine-net` bridge network and is unreachable from outside.

---

## 2. The Bridge Network — `routine-net`

```mermaid
graph LR
    subgraph routine-net["Bridge Network: routine-net (driver: bridge)"]
        direction TB
        nginx_c["nginx"]
        frontend_c["frontend"]
        backend_c["backend"]
        db_c["db"]
    end

    nginx_c <-->|DNS: frontend| frontend_c
    nginx_c <-->|DNS: backend| backend_c
    backend_c <-->|DNS: db| db_c
```

**How it works:**

| Property | Detail |
|---|---|
| Driver | `bridge` — Docker's default software switch, isolated from the host network |
| Name | `routine-net` (defined once under `networks:` in `docker-compose.yml`) |
| DNS resolution | Docker embeds a DNS resolver; each service is reachable by its **service name** (e.g., `db`, `backend`, `frontend`) |
| Isolation | Containers NOT on `routine-net` cannot reach these services at all |

All four services attach to this single network:

```yaml
# docker-compose.yml (excerpt)
networks:
  routine-net:
    driver: bridge
```

Each service opts in with:
```yaml
networks:
  - routine-net
```

---

## 3. Port Strategy — `ports` vs `expose`

```mermaid
graph LR
    subgraph Host
        H80["localhost:80"]
    end

    subgraph routine-net
        N["nginx :80"]
        F["frontend :80"]
        B["backend :5000"]
        D["db :5432"]
    end

    H80 -->|ports: 80:80\npublished to host| N
    N -->|expose only\ninvisible to host| F
    N -->|expose only\ninvisible to host| B
    B -->|expose only\ninvisible to host| D

    style H80 fill:#f9f,stroke:#333
    style N fill:#bbf,stroke:#333
    style F fill:#bfb,stroke:#333
    style B fill:#bfb,stroke:#333
    style D fill:#bfb,stroke:#333
```

| Service | Directive | Ports | Visible outside Docker? |
|---|---|---|---|
| `nginx` | `ports: "80:80"` | Host 80 → Container 80 | **Yes** — the only public entry point |
| `frontend` | `expose: "80"` | Container 80 (internal) | No |
| `backend` | `expose: "5000"` | Container 5000 (internal) | No |
| `db` | *(neither)* | Container 5432 (internal) | No |

> `expose` is documentation-only metadata. It does **not** publish a port to the host; it signals to other containers (and `docker-compose`) that this port is in use.

---

## 4. Nginx — Reverse Proxy & Traffic Router

Nginx is the single public gateway. It uses **named upstreams** that resolve via Docker DNS:

```mermaid
sequenceDiagram
    participant Browser
    participant Nginx as nginx:80
    participant Frontend as frontend:80
    participant Backend as backend:5000

    Browser->>Nginx: GET /  (or any non-API path)
    Nginx->>Frontend: proxy_pass http://frontend
    Frontend-->>Nginx: HTML / JS / CSS
    Nginx-->>Browser: Response

    Browser->>Nginx: GET /api/tasks
    Nginx->>Backend: proxy_pass http://backend
    Backend-->>Nginx: JSON
    Nginx-->>Browser: JSON Response
```

**Routing rules from `nginx.conf`:**

```
location /api  →  proxy_pass http://backend   (Flask on :5000)
location /     →  proxy_pass http://frontend  (Vite/Nginx on :80)
```

Nginx also forwards important headers so the backend knows the real client:

```nginx
proxy_set_header Host              $host;
proxy_set_header X-Real-IP         $remote_addr;
proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
proxy_set_header X-Forwarded-Proto $scheme;
```

---

## 5. Backend → Database Connection

The Flask backend connects to PostgreSQL using environment variables injected by Docker Compose:

```mermaid
sequenceDiagram
    participant Backend as backend (routine-backend)
    participant DNS as Docker DNS
    participant DB as db (routine-db) :5432

    Backend->>DNS: resolve "db"
    DNS-->>Backend: 172.x.x.x (container IP)
    Backend->>DB: TCP connect :5432\n(psycopg2)
    DB-->>Backend: connection established
    Backend->>DB: SQL queries
    DB-->>Backend: result rows
```

**Environment variables that drive the connection:**

```yaml
# docker-compose.yml (backend service)
environment:
  - POSTGRES_HOST=db        # ← Docker DNS name of the db service
  - POSTGRES_PORT=5432
  - POSTGRES_DB=tasksdb
  - POSTGRES_USER=tasksuser
  - POSTGRES_PASSWORD=taskspass
```

The host name `db` works because both containers share `routine-net`. Docker's embedded DNS resolves the service name `db` to the container's internal IP automatically.

---

## 6. Service Startup & Dependency Order

```mermaid
graph TD
    db["db\n(PostgreSQL)"]
    backend["backend\n(Flask)"]
    frontend["frontend\n(React/Nginx)"]
    nginx["nginx\n(Reverse Proxy)"]

    db -->|"healthcheck:\npg_isready passes"| backend
    frontend -->|"depends_on"| nginx
    backend  -->|"depends_on"| nginx
```

| Dependency | Mechanism | Why |
|---|---|---|
| `backend` waits for `db` | `depends_on` with `condition: service_healthy` | Prevents Flask from crashing on startup because Postgres isn't ready yet |
| `nginx` waits for `frontend` & `backend` | `depends_on` (service started) | Ensures upstream targets exist before Nginx begins accepting traffic |

The `db` healthcheck uses `pg_isready`:
```yaml
healthcheck:
  test: ["CMD-SHELL", "pg_isready -U tasksuser -d tasksdb"]
  interval: 5s
  timeout: 5s
  retries: 10
```

---

## 7. Persistent Storage — Named Volume

```mermaid
graph LR
    db_c["db container\n/var/lib/postgresql/data"]
    vol[("postgres_data\nNamed Volume\n(host-managed)")]

    db_c <-->|bind mount| vol
```

The volume is declared outside any service so it persists across `docker compose down / up` cycles:

```yaml
volumes:
  postgres_data:   # top-level — not tied to container lifecycle
```

Mounted inside the `db` service:
```yaml
volumes:
  - postgres_data:/var/lib/postgresql/data
```

This is **not** a networking concern, but it affects availability: the database survives container recreation, so the backend always finds its data intact on reconnect.

---

## 8. Complete Request Lifecycle

```mermaid
sequenceDiagram
    actor User as User (Browser)
    participant H as Host :80
    participant N as nginx\nroutine-net
    participant F as frontend\nroutine-net
    participant B as backend\nroutine-net
    participant D as db\nroutine-net

    User->>H: GET http://localhost/
    H->>N: forwarded via port mapping
    N->>F: proxy_pass (location /)
    F-->>N: index.html + JS bundle
    N-->>User: page rendered in browser

    User->>H: fetch("/api/tasks")
    H->>N: forwarded via port mapping
    N->>B: proxy_pass (location /api)
    B->>D: SELECT * FROM tasks
    D-->>B: rows
    B-->>N: JSON array
    N-->>User: JSON response
```

---

## 9. Summary Table

| Container | Network | Published Port | Internal Port | Communicates With |
|---|---|---|---|---|
| `routine-nginx` | `routine-net` | **80** (host) | 80 | `frontend`, `backend` |
| `routine-frontend` | `routine-net` | none | 80 | — |
| `routine-backend` | `routine-net` | none | 5000 | `db` |
| `routine-db` | `routine-net` | none | 5432 | — |
