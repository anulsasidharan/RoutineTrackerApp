import React, { useEffect, useState } from "react";
import AddTask from "./components/AddTask";
import TaskList from "./components/TaskList";
import { createTask, deleteTask, fetchTasks, updateTask } from "./api";
import "./App.css";

export default function App() {
  const [tasks, setTasks] = useState([]);
  const [filter, setFilter] = useState("all");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    loadTasks();
  }, []);

  async function loadTasks() {
    try {
      setLoading(true);
      setTasks(await fetchTasks());
    } catch {
      setError("Could not load tasks. Is the backend running?");
    } finally {
      setLoading(false);
    }
  }

  async function handleAdd(title, description) {
    try {
      const task = await createTask(title, description);
      setTasks((prev) => [...prev, task]);
    } catch {
      setError("Failed to add task.");
    }
  }

  async function handleToggle(id, completed) {
    try {
      const updated = await updateTask(id, { completed: !completed });
      setTasks((prev) => prev.map((t) => (t.id === id ? updated : t)));
    } catch {
      setError("Failed to update task.");
    }
  }

  async function handleDelete(id) {
    try {
      await deleteTask(id);
      setTasks((prev) => prev.filter((t) => t.id !== id));
    } catch {
      setError("Failed to delete task.");
    }
  }

  async function handleUpdate(id, updates) {
    try {
      const updated = await updateTask(id, updates);
      setTasks((prev) => prev.map((t) => (t.id === id ? updated : t)));
    } catch {
      setError("Failed to update task.");
    }
  }

  const filtered = tasks.filter((t) => {
    if (filter === "active") return !t.completed;
    if (filter === "completed") return t.completed;
    return true;
  });

  const doneCount = tasks.filter((t) => t.completed).length;

  return (
    <div className="app">
      <div className="container">
        <header className="header">
          <h1>Routine Tracker</h1>
          <p className="subtitle">
            {doneCount} / {tasks.length} completed
          </p>
        </header>

        <AddTask onAdd={handleAdd} />

        {error && (
          <div className="error-banner" role="alert">
            <span>{error}</span>
            <button onClick={() => setError(null)} aria-label="Dismiss">✕</button>
          </div>
        )}

        <div className="filters">
          {["all", "active", "completed"].map((f) => (
            <button
              key={f}
              className={`filter-btn${filter === f ? " active" : ""}`}
              onClick={() => setFilter(f)}
            >
              {f[0].toUpperCase() + f.slice(1)}
            </button>
          ))}
        </div>

        {loading ? (
          <p className="status-msg">Loading…</p>
        ) : (
          <TaskList tasks={filtered} onToggle={handleToggle} onDelete={handleDelete} onUpdate={handleUpdate} />
        )}
      </div>
    </div>
  );
}
