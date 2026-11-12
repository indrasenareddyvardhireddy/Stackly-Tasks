import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import FormField from './FormField.jsx';
import Loader from './Loader.jsx';
import { listCategories } from '../api/categoryApi.js';
import { parseApiError, todayISO } from '../utils/errors.js';
import { useToast } from '../context/ToastContext.jsx';

const EMPTY = {
  title: '', description: '', category: '', priority: 'Medium',
  status: 'To Do', due_date: '', recurrence: 'none',
};

// Used by both the create and the edit page.
export default function TaskForm({ initialValues, onSubmit, submitLabel = 'Save task', isEdit = false }) {
  const toast = useToast();
  const [values, setValues] = useState({ ...EMPTY, ...initialValues });
  const [categories, setCategories] = useState([]);
  const [loadingCats, setLoadingCats] = useState(true);
  const [errors, setErrors] = useState({});
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    listCategories()
      .then(setCategories)
      .catch(() => toast.error('Could not load categories.'))
      .finally(() => setLoadingCats(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // On edit, initialValues (the task's current values) fill the form via the useState initialiser above.

  const set = (name) => (e) => setValues((v) => ({ ...v, [name]: e.target.value }));

  const validate = () => {
    const errs = {};
    const title = values.title.trim();
    if (!title) errs.title = 'Title is required.';
    else if (title.length < 3) errs.title = 'Title must be at least 3 characters.';
    else if (title.length > 100) errs.title = 'Title must be at most 100 characters.';
    if (!isEdit && values.due_date && values.due_date < todayISO()) errs.due_date = 'Due date cannot be in the past.';
    return errs;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    const clientErrors = validate();
    setErrors(clientErrors);
    if (Object.keys(clientErrors).length) return;

    setSubmitting(true);
    try {
      await onSubmit({
        title: values.title.trim(),
        description: values.description,
        category: values.category ? Number(values.category) : null,
        priority: values.priority,
        status: values.status,
        due_date: values.due_date || null,
        recurrence: values.recurrence,
      });
    } catch (err) {
      const { message, fieldErrors } = parseApiError(err);
      setErrors(fieldErrors);
      toast.error(message);
    } finally {
      setSubmitting(false);
    }
  };

  if (loadingCats) return <Loader />;

  return (
    <form className="card form" onSubmit={handleSubmit} noValidate>
      <FormField label="Title" error={errors.title}>
        <input className="input" value={values.title} onChange={set('title')} maxLength={100} placeholder="What needs to be done?" />
      </FormField>
      <FormField label="Description" error={errors.description}>
        <textarea className="input" rows={4} value={values.description} onChange={set('description')} />
      </FormField>
      <div className="grid-2">
        <FormField label="Category" error={errors.category}>
          <select className="input" value={values.category ?? ''} onChange={set('category')}>
            <option value="">No category</option>
            {categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        </FormField>
        <FormField label="Due date" error={errors.due_date}>
          <input type="date" className="input" value={values.due_date || ''} onChange={set('due_date')} />
        </FormField>
        <FormField label="Priority" error={errors.priority}>
          <select className="input" value={values.priority} onChange={set('priority')}>
            <option>Low</option><option>Medium</option><option>High</option>
          </select>
        </FormField>
        <FormField label="Status" error={errors.status}>
          <select className="input" value={values.status} onChange={set('status')}>
            <option>To Do</option><option>In Progress</option><option>Done</option>
          </select>
        </FormField>
        <FormField label="Repeat" error={errors.recurrence}>
          <select className="input" value={values.recurrence} onChange={set('recurrence')}>
            <option value="none">Does not repeat</option>
            <option value="daily">Daily</option>
            <option value="weekly">Weekly</option>
          </select>
        </FormField>
      </div>
      {categories.length === 0 && (
        <p className="muted small">You have no categories yet. <Link to="/categories">Create one</Link> to organise your tasks.</p>
      )}
      <div className="row end">
        <Link className="btn" to="/tasks">Cancel</Link>
        <button className="btn btn-primary" type="submit" disabled={submitting}>
          {submitting ? 'Saving…' : submitLabel}
        </button>
      </div>
    </form>
  );
}
