import React, { useState } from "react";

export default function AddTask({ onAdd }) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [showDesc, setShowDesc] = useState(false);

  function handleSubmit(e) {
    e.preventDefault();
    const trimmed = title.trim();
    if (!trimmed) return;
    onAdd(trimmed, description.trim());
    setTitle("");
    setDescription("");
    setShowDesc(false);
  }

  return (
    <form className="add-form" onSubmit={handleSubmit}>
      <div className="add-form-row">
        <input
          className="task-input"
          type="text"
          placeholder="What needs to be done?"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          aria-label="New task title"
        />
        <button className="add-btn" type="submit">
          Add Task
        </button>
      </div>

      <button
        type="button"
        className="toggle-desc-btn"
        onClick={() => setShowDesc((v) => !v)}
      >
        {showDesc ? "▲ Hide description" : "+ Add description"}
      </button>

      {showDesc && (
        <textarea
          className="desc-input"
          placeholder="Add a description (optional)…"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          rows={3}
          aria-label="Task description"
        />
      )}
    </form>
  );
}
