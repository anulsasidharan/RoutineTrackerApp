const BASE = "/api/tasks";

export async function fetchTasks() {
  const res = await fetch(BASE);
  if (!res.ok) throw new Error("Failed to fetch tasks");
  return res.json();
}

export async function createTask(title, description = "") {
  const res = await fetch(BASE, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title, description }),
  });
  if (!res.ok) throw new Error("Failed to create task");
  return res.json();
}

export async function updateTask(id, updates) {
  const res = await fetch(`${BASE}/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(updates),
  });
  if (!res.ok) throw new Error("Failed to update task");
  return res.json();
}

export async function deleteTask(id) {
  const res = await fetch(`${BASE}/${id}`, { method: "DELETE" });
  if (!res.ok && res.status !== 204) throw new Error("Failed to delete task");
}
