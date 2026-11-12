import { useState } from 'react';
import TaskCard from './TaskCard.jsx';

const COLUMNS = ['To Do', 'In Progress', 'Done'];

export default function KanbanBoard({ tasks, onStatusChange, onToggle, onDelete }) {
  const [overColumn, setOverColumn] = useState(null);

  const handleDrop = (e, status) => {
    e.preventDefault();
    setOverColumn(null);
    const id = Number(e.dataTransfer.getData('text/plain'));
    const task = tasks.find((t) => t.id === id);
    if (task && task.status !== status) onStatusChange(task, status);
  };

  return (
    <div className="kanban">
      {COLUMNS.map((status) => {
        const items = tasks.filter((t) => t.status === status);
        return (
          <section
            key={status}
            className={`kanban-col ${overColumn === status ? 'drop' : ''}`}
            onDragOver={(e) => { e.preventDefault(); setOverColumn(status); }}
            onDragLeave={() => setOverColumn(null)}
            onDrop={(e) => handleDrop(e, status)}
          >
            <h3>{status} <span className="count">{items.length}</span></h3>
            {items.length === 0 && <p className="muted small">Drop tasks here</p>}
            {items.map((task) => (
              <div
                key={task.id}
                draggable
                onDragStart={(e) => e.dataTransfer.setData('text/plain', String(task.id))}
                className="kanban-item"
              >
                <TaskCard task={task} compact onToggle={onToggle} onDelete={onDelete} />
                {/* touch devices cannot drag, so offer a select as well */}
                <select
                  className="input small-select"
                  value={task.status}
                  onChange={(e) => onStatusChange(task, e.target.value)}
                  aria-label="Move task to"
                >
                  {COLUMNS.map((c) => <option key={c}>{c}</option>)}
                </select>
              </div>
            ))}
          </section>
        );
      })}
    </div>
  );
}
