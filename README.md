# Routine Tracker App

A lightweight, fully-containerised routine-management application built with a clean 3-container architecture.

## Architecture

```
Browser
   │
   ▼
┌─────────────────────────────────────┐
│         Nginx  (port 80)            │  ← only public port
│         Reverse Proxy               │
└────────────┬─────────────┬──────────┘
             │             │
             ▼             ▼
      ┌──────────┐  ┌────────────────┐
      │ Frontend │  │    Backend     │
      │  React   │  │  Python/Flask  │
      │ (Nginx)  │  │  + SQLite DB   │
      └──────────┘  └────────────────┘
```

| Container       | Technology          | Internal port |
|-----------------|---------------------|---------------|
| `routine-nginx`    | Nginx (proxy)       | 80 (public)   |
| `routine-frontend` | React + Vite → Nginx| 80            |
| `routine-backend`  | Python Flask        | 5000          |

## Quick Start

```bash
# Build and start all 3 containers
docker compose up --build

# Open in browser
http://localhost
```

To stop:
```bash
docker compose down
```

To stop and remove the database volume:
```bash
docker compose down -v
```

## API Reference

| Method   | Endpoint              | Description         |
|----------|-----------------------|---------------------|
| `GET`    | `/api/tasks`          | List all tasks      |
| `POST`   | `/api/tasks`          | Create a task       |
| `PUT`    | `/api/tasks/:id`      | Toggle / update task|
| `DELETE` | `/api/tasks/:id`      | Delete a task       |
| `GET`    | `/api/health`         | Health check        |

### Example

```bash
# Add a task
curl -X POST http://localhost/api/tasks \
     -H "Content-Type: application/json" \
     -d '{"title": "Buy groceries"}'

# Mark complete
curl -X PUT http://localhost/api/tasks/<id> \
     -H "Content-Type: application/json" \
     -d '{"completed": true}'

# Delete
curl -X DELETE http://localhost/api/tasks/<id>
```

## Project Structure

```
Routine_Tracker_App/
├── docker-compose.yml
├── backend/
│   ├── app.py            # Flask REST API
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── index.html
│   ├── vite.config.js
│   ├── package.json
│   ├── Dockerfile
│   └── src/
│       ├── main.jsx
│       ├── App.jsx / App.css
│       ├── index.css
│       ├── api.js
│       └── components/
│           ├── AddTask.jsx
│           ├── TaskList.jsx
│           └── TaskItem.jsx
└── nginx/
    ├── nginx.conf
    └── Dockerfile
```

## Local Development (without Docker)

**Backend**
```bash
cd backend
pip install -r requirements.txt
python app.py          # runs on http://localhost:5000
```

**Frontend**
```bash
cd frontend
npm install
npm run dev            # runs on http://localhost:3000
                       # vite.config.js proxies /api → localhost:5000
```
# RoutineTrackerApp
