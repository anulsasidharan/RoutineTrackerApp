import React from "react";
import TaskItem from "./TaskItem";

export default function TaskList({ tasks, onToggle, onDelete, onUpdate }) {
  if (tasks.length === 0) {
    return <p className="empty-msg">No tasks here.</p>;
  }

  return (
    <ul className="task-list">
      {tasks.map((task) => (
        <TaskItem
          key={task.id}
          task={task}
          onToggle={onToggle}
          onDelete={onDelete}
          onUpdate={onUpdate}
        />
      ))}
    </ul>
  );
}
