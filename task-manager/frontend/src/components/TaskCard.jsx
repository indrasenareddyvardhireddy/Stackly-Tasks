import { Link } from 'react-router-dom';
import { formatDate } from '../utils/errors.js';

export default function TaskCard({ task, onToggle, onDelete, compact = false }) {
  const done = task.status === 'Done';
  const subDone = task.subtasks?.filter((s) => s.is_done).length ?? 0;
  const subTotal = task.subtasks?.length ?? 0;

  return (
    <article className={`task-card ${task.is_overdue ? 'overdue' : ''} ${done ? 'is-done' : ''}`}>
      <input
        type="checkbox"
        className="check"
        checked={done}
        onChange={() => onToggle(task)}
        aria-label={done ? 'Mark as not done' : 'Mark as done'}
      />
      <div className="task-main">
        <h4 className="task-title">{task.title}</h4>
        <div className="meta">
          {task.category_detail && (
            <span className="chip" style={{ '--chip': task.category_detail.color }}>
              <i className="dot" /> {task.category_detail.name}
            </span>
          )}
          <span className={`badge priority-${task.priority.toLowerCase()}`}>{task.priority}</span>
          {!compact && <span className={`badge status-${task.status.replace(' ', '').toLowerCase()}`}>{task.status}</span>}
          <span className="due">
            {task.is_overdue ? 'Overdue · ' : ''}
            {formatDate(task.due_date)}
          </span>
          {task.recurrence !== 'none' && <span className="badge">Repeats {task.recurrence}</span>}
          {subTotal > 0 && <span className="badge">{subDone}/{subTotal} subtasks</span>}
        </div>
      </div>
      <div className="task-actions">
        <Link className="btn btn-small" to={`/tasks/${task.id}/edit`}>Edit</Link>
        {onDelete && <button className="btn btn-small btn-danger-outline" onClick={() => onDelete(task)}>Delete</button>}
      </div>
    </article>
  );
}
