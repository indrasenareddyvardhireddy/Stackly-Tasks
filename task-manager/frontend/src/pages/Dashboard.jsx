import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import Loader from '../components/Loader.jsx';
import TaskCard from '../components/TaskCard.jsx';
import { getDashboard, toggleComplete } from '../api/taskApi.js';
import { useToast } from '../context/ToastContext.jsx';
import { parseApiError } from '../utils/errors.js';

export default function Dashboard() {
  const toast = useToast();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      setData(await getDashboard());
    } catch (err) {
      toast.error(parseApiError(err).message);
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleToggle = async (task) => {
    try {
      const updated = await toggleComplete(task.id);
      toast.success(updated.status === 'Done' ? 'Task completed.' : 'Task reopened.');
      load(); // dashboard updates
    } catch (err) {
      toast.error(parseApiError(err).message);
    }
  };

  if (loading) return <Loader />;
  if (!data) return null;

  const stats = [
    ['Total', data.total, ''],
    ['To Do', data.todo, ''],
    ['In Progress', data.in_progress, ''],
    ['Done', data.done, 'good'],
    ['Overdue', data.overdue, data.overdue ? 'bad' : ''],
    ['Due today', data.due_today, data.due_today ? 'warn' : ''],
  ];

  return (
    <>
      <div className="page-head">
        <h1>Dashboard</h1>
        <Link className="btn btn-primary" to="/tasks/new">New task</Link>
      </div>

      {data.total === 0 ? (
        <div className="card empty">
          <p>No tasks yet. Create your first task!</p>
          <Link className="btn btn-primary" to="/tasks/new">Create task</Link>
        </div>
      ) : (
        <>
          <section className="stats">
            {stats.map(([label, value, tone]) => (
              <div key={label} className={`card stat ${tone}`}>
                <span className="stat-value">{value}</span>
                <span className="stat-label">{label}</span>
              </div>
            ))}
          </section>

          <section className="card">
            <div className="row between">
              <h3>Completion</h3>
              <strong>{data.completion_percentage}%</strong>
            </div>
            <div className="progress" role="progressbar" aria-valuenow={data.completion_percentage} aria-valuemin={0} aria-valuemax={100}>
              <div className="progress-bar" style={{ width: `${data.completion_percentage}%` }} />
            </div>
          </section>

          <div className="grid-2 top">
            <section className="card">
              <h3>Overdue</h3>
              {data.overdue_tasks.length === 0 && <p className="muted small">Nothing overdue. Nice work.</p>}
              <div className="stack">
                {data.overdue_tasks.map((t) => <TaskCard key={t.id} task={t} compact onToggle={handleToggle} />)}
              </div>
            </section>
            <section className="card">
              <h3>Due today</h3>
              {data.due_today_tasks.length === 0 && <p className="muted small">Nothing due today.</p>}
              <div className="stack">
                {data.due_today_tasks.map((t) => <TaskCard key={t.id} task={t} compact onToggle={handleToggle} />)}
              </div>
            </section>
          </div>

          <section className="card">
            <h3>Tasks per category</h3>
            <ul className="cat-counts">
              {data.categories.map((c) => (
                <li key={`${c.id}-${c.name}`}>
                  <span className="chip" style={{ '--chip': c.color }}><i className="dot" /> {c.name}</span>
                  <strong>{c.count}</strong>
                </li>
              ))}
            </ul>
          </section>
        </>
      )}
    </>
  );
}
