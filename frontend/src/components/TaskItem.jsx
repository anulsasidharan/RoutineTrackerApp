import React, { useState } from "react";

export default function TaskItem({ task, onToggle, onDelete, onUpdate }) {
  const [editingDesc, setEditingDesc] = useState(false);
  const [descValue, setDescValue] = useState("");

  function startEditing() {
    setDescValue(task.description || "");
    setEditingDesc(true);
  }

  function handleSave() {
    onUpdate(task.id, { description: descValue.trim() });
    setEditingDesc(false);
  }

  function handleCancel() {
    setEditingDesc(false);
  }

  return (
    <li className={`task-item${task.completed ? " done" : ""}`}>
      {/* ── Main row: checkbox + title + delete ── */}
      <div className="task-main">
        <input
          className="task-checkbox"
          type="checkbox"
          checked={task.completed}
          onChange={() => onToggle(task.id, task.completed)}
          aria-label={`Mark "${task.title}" as ${task.completed ? "incomplete" : "complete"}`}
        />
        <span className="task-title">{task.title}</span>
        <button
          className="delete-btn"
          onClick={() => onDelete(task.id)}
          aria-label={`Delete "${task.title}"`}
        >
          ✕
        </button>
      </div>

      {/* ── Description area ── */}
      {editingDesc ? (
        <div className="desc-edit-area">
          <textarea
            className="desc-textarea"
            value={descValue}
            onChange={(e) => setDescValue(e.target.value)}
            rows={3}
            autoFocus
            placeholder="Add a description…"
          />
          <div className="desc-actions">
            <button className="desc-save-btn" type="button" onClick={handleSave}>
              Save
            </button>
            <button className="desc-cancel-btn" type="button" onClick={handleCancel}>
              Cancel
            </button>
          </div>
        </div>
      ) : task.description ? (
        <div className="task-desc-row">
          <p className="task-description">{task.description}</p>
          <button
            className="edit-desc-btn"
            type="button"
            onClick={startEditing}
            aria-label="Edit description"
          >
            ✏️
          </button>
        </div>
      ) : (
        <button
          className="add-desc-hint"
          type="button"
          onClick={startEditing}
        >
          + Add description
        </button>
      )}
    </li>
  );
}
