import { useState } from 'react';
import { addSubtask, deleteSubtask, updateSubtask } from '../api/taskApi.js';
import { parseApiError } from '../utils/errors.js';
import { useToast } from '../context/ToastContext.jsx';

// Checklist inside a task (bonus). Works on saved tasks, so it lives on the edit page.
export default function SubtaskList({ taskId, initial }) {
  const toast = useToast();
  const [items, setItems] = useState(initial || []);
  const [title, setTitle] = useState('');
  const [busy, setBusy] = useState(false);

  const add = async (e) => {
    e.preventDefault();
    if (!title.trim()) return;
    setBusy(true);
    try {
      const created = await addSubtask(taskId, title.trim());
      setItems((list) => [...list, created]);
      setTitle('');
    } catch (err) {
      toast.error(parseApiError(err).message);
    } finally {
      setBusy(false);
    }
  };

  const toggle = async (item) => {
    try {
      const updated = await updateSubtask(taskId, item.id, { is_done: !item.is_done });
      setItems((list) => list.map((s) => (s.id === item.id ? updated : s)));
    } catch (err) {
      toast.error(parseApiError(err).message);
    }
  };

  const remove = async (item) => {
    try {
      await deleteSubtask(taskId, item.id);
      setItems((list) => list.filter((s) => s.id !== item.id));
    } catch (err) {
      toast.error(parseApiError(err).message);
    }
  };

  const done = items.filter((s) => s.is_done).length;

  return (
    <section className="card">
      <h3>Subtasks {items.length > 0 && <span className="muted small">({done}/{items.length} done)</span>}</h3>
      {items.length === 0 && <p className="muted small">No subtasks yet. Break this task into smaller steps.</p>}
      <ul className="subtasks">
        {items.map((s) => (
          <li key={s.id} className={s.is_done ? 'is-done' : ''}>
            <label>
              <input type="checkbox" checked={s.is_done} onChange={() => toggle(s)} /> <span>{s.title}</span>
            </label>
            <button className="btn btn-small btn-ghost" onClick={() => remove(s)} aria-label={`Remove ${s.title}`}>Remove</button>
          </li>
        ))}
      </ul>
      <form className="row" onSubmit={add}>
        <input className="input" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Add a subtask" maxLength={200} />
        <button className="btn" type="submit" disabled={busy}>Add</button>
      </form>
    </section>
  );
}
