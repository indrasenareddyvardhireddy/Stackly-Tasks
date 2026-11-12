import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import ConfirmDialog from '../components/ConfirmDialog.jsx';
import KanbanBoard from '../components/KanbanBoard.jsx';
import Loader from '../components/Loader.jsx';
import TaskCard from '../components/TaskCard.jsx';
import { listCategories } from '../api/categoryApi.js';
import { deleteTask, listTasks, patchTask, toggleComplete } from '../api/taskApi.js';
import { useToast } from '../context/ToastContext.jsx';
import { parseApiError } from '../utils/errors.js';

const PAGE_SIZE = 10;
const FILTER_KEYS = ['search', 'status', 'priority', 'category', 'due'];

export default function Tasks() {
  const toast = useToast();
  // All filters live in the URL, so refresh / back / sharing keep the same view.
  const [sp, setSp] = useSearchParams();
  const [data, setData] = useState({ count: 0, next: null, previous: null, results: [] });
  const [categories, setCategories] = useState([]);
  const [loading, setLoading] = useState(true);
  const [reload, setReload] = useState(0);
  const [toDelete, setToDelete] = useState(null);
  const [deleting, setDeleting] = useState(false);
  const [searchText, setSearchText] = useState(sp.get('search') || '');
  const pushedSearch = useRef(sp.get('search') || '');

  const view = sp.get('view') === 'board' ? 'board' : 'list';
  const page = Number(sp.get('page')) || 1;
  const ordering = sp.get('ordering') || '-created_at';
  const filtersActive = FILTER_KEYS.some((k) => sp.get(k));

  const setParam = useCallback(
    (key, value) => {
      setSp((prev) => {
        const next = new URLSearchParams(prev);
        if (value) next.set(key, value);
        else next.delete(key);
        if (key !== 'page') next.delete('page'); // any filter change goes back to page 1
        return next;
      });
    },
    [setSp]
  );

  useEffect(() => {
    listCategories().then(setCategories).catch(() => {});
  }, []);

  // Debounce: search 500 ms after the user stops typing.
  useEffect(() => {
    const timer = setTimeout(() => {
      const trimmed = searchText.trim();
      if (trimmed !== (sp.get('search') || '')) {
        pushedSearch.current = trimmed;
        setParam('search', trimmed);
      }
    }, 500);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchText]);

  // Browser back/forward changes the URL: mirror it into the box.
  const urlSearch = sp.get('search') || '';
  useEffect(() => {
    if (urlSearch !== pushedSearch.current) {
      pushedSearch.current = urlSearch;
      setSearchText(urlSearch);
    }
  }, [urlSearch]);

  const query = sp.toString();
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    const params = { ordering };
    FILTER_KEYS.forEach((k) => { if (sp.get(k)) params[k] = sp.get(k); });
    if (view === 'board') params.page_size = 100;
    else params.page = page;

    listTasks(params)
      .then((res) => { if (!cancelled) setData(res); })
      .catch((err) => {
        if (cancelled) return;
        if (err.response?.status === 404 && page > 1) setParam('page', '1');
        else toast.error(parseApiError(err).message);
      })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query, reload]);

  const replaceTask = (updated) =>
    setData((d) => ({ ...d, results: d.results.map((t) => (t.id === updated.id ? updated : t)) }));

  const handleToggle = async (task) => {
    try {
      const updated = await toggleComplete(task.id);
      replaceTask(updated);
      toast.success(updated.status === 'Done' ? 'Task completed.' : 'Task reopened.');
    } catch (err) {
      toast.error(parseApiError(err).message);
    }
  };

  const handleStatusChange = async (task, status) => {
    const before = task;
    replaceTask({ ...task, status }); // optimistic
    try {
      replaceTask(await patchTask(task.id, { status }));
      toast.success(`Moved to ${status}.`);
    } catch (err) {
      replaceTask(before);
      toast.error(parseApiError(err).message);
    }
  };

  const confirmDelete = async () => {
    setDeleting(true);
    try {
      await deleteTask(toDelete.id);
      toast.success('Task deleted.');
      setToDelete(null);
      if (data.results.length === 1 && page > 1 && view === 'list') setParam('page', String(page - 1));
      else setReload((n) => n + 1);
    } catch (err) {
      toast.error(parseApiError(err).message);
    } finally {
      setDeleting(false);
    }
  };

  const clearFilters = () => {
    setSearchText('');
    pushedSearch.current = '';
    setSp((prev) => {
      const next = new URLSearchParams();
      if (prev.get('view')) next.set('view', prev.get('view'));
      return next;
    });
  };

  const totalPages = Math.max(1, Math.ceil(data.count / PAGE_SIZE));

  return (
    <>
      <div className="page-head">
        <h1>Tasks</h1>
        <div className="row">
          <div className="segmented" role="group" aria-label="View">
            <button className={view === 'list' ? 'on' : ''} onClick={() => setParam('view', '')}>List</button>
            <button className={view === 'board' ? 'on' : ''} onClick={() => setParam('view', 'board')}>Board</button>
          </div>
          <Link className="btn btn-primary" to="/tasks/new">New task</Link>
        </div>
      </div>

      <section className="card filters">
        <input
          className="input grow"
          type="search"
          placeholder="Search title or description"
          value={searchText}
          onChange={(e) => setSearchText(e.target.value)}
        />
        <select className="input" value={sp.get('status') || ''} onChange={(e) => setParam('status', e.target.value)} aria-label="Status">
          <option value="">All statuses</option>
          <option>To Do</option><option>In Progress</option><option>Done</option>
        </select>
        <select className="input" value={sp.get('priority') || ''} onChange={(e) => setParam('priority', e.target.value)} aria-label="Priority">
          <option value="">All priorities</option>
          <option>Low</option><option>Medium</option><option>High</option>
        </select>
        <select className="input" value={sp.get('category') || ''} onChange={(e) => setParam('category', e.target.value)} aria-label="Category">
          <option value="">All categories</option>
          {categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
        <select className="input" value={sp.get('due') || ''} onChange={(e) => setParam('due', e.target.value)} aria-label="Due">
          <option value="">Any due date</option>
          <option value="today">Today</option>
          <option value="overdue">Overdue</option>
          <option value="upcoming">Upcoming</option>
        </select>
        <select className="input" value={ordering} onChange={(e) => setParam('ordering', e.target.value === '-created_at' ? '' : e.target.value)} aria-label="Sort by">
          <option value="-created_at">Newest first</option>
          <option value="created_at">Oldest first</option>
          <option value="due_date">Due date (soonest)</option>
          <option value="-due_date">Due date (latest)</option>
          <option value="-priority">Priority (high to low)</option>
          <option value="priority">Priority (low to high)</option>
        </select>
        {filtersActive && <button className="btn btn-ghost" onClick={clearFilters}>Clear filters</button>}
      </section>

      {loading ? (
        <Loader />
      ) : data.results.length === 0 ? (
        <div className="card empty">
          {filtersActive ? (
            <p>No tasks match these filters.</p>
          ) : (
            <>
              <p>No tasks yet. Create your first task!</p>
              <Link className="btn btn-primary" to="/tasks/new">Create task</Link>
            </>
          )}
        </div>
      ) : view === 'board' ? (
        <KanbanBoard tasks={data.results} onStatusChange={handleStatusChange} onToggle={handleToggle} onDelete={setToDelete} />
      ) : (
        <>
          <div className="stack">
            {data.results.map((task) => (
              <TaskCard key={task.id} task={task} onToggle={handleToggle} onDelete={setToDelete} />
            ))}
          </div>
          <div className="pagination">
            <button className="btn" disabled={!data.previous} onClick={() => setParam('page', String(page - 1))}>Previous</button>
            <span>Page {page} of {totalPages}</span>
            <button className="btn" disabled={!data.next} onClick={() => setParam('page', String(page + 1))}>Next</button>
          </div>
        </>
      )}

      <ConfirmDialog
        open={Boolean(toDelete)}
        title="Delete this task?"
        message={toDelete ? `"${toDelete.title}" will be permanently removed.` : ''}
        busy={deleting}
        onConfirm={confirmDelete}
        onCancel={() => setToDelete(null)}
      />
    </>
  );
}
