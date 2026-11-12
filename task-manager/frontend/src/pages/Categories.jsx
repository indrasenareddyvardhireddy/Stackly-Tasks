import { useEffect, useState } from 'react';
import ConfirmDialog from '../components/ConfirmDialog.jsx';
import FormField from '../components/FormField.jsx';
import Loader from '../components/Loader.jsx';
import { createCategory, deleteCategory, listCategories, updateCategory } from '../api/categoryApi.js';
import { useToast } from '../context/ToastContext.jsx';
import { parseApiError } from '../utils/errors.js';

const BLANK = { name: '', color: '#4F46E5' };

export default function Categories() {
  const toast = useToast();
  const [categories, setCategories] = useState([]);
  const [loading, setLoading] = useState(true);
  const [values, setValues] = useState(BLANK);
  const [editingId, setEditingId] = useState(null);
  const [errors, setErrors] = useState({});
  const [submitting, setSubmitting] = useState(false);
  const [toDelete, setToDelete] = useState(null);
  const [deleting, setDeleting] = useState(false);

  const load = async () => {
    try {
      setCategories(await listCategories());
    } catch (err) {
      toast.error(parseApiError(err).message);
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => { load(); // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const reset = () => { setValues(BLANK); setEditingId(null); setErrors({}); };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!values.name.trim()) { setErrors({ name: 'Name is required.' }); return; }
    setSubmitting(true);
    try {
      if (editingId) await updateCategory(editingId, { name: values.name.trim(), color: values.color });
      else await createCategory({ name: values.name.trim(), color: values.color });
      toast.success(editingId ? 'Category updated.' : 'Category added.');
      reset();
      await load();
    } catch (err) {
      const { message, fieldErrors } = parseApiError(err);
      setErrors(fieldErrors);
      toast.error(message);
    } finally {
      setSubmitting(false);
    }
  };

  const startEdit = (c) => { setEditingId(c.id); setValues({ name: c.name, color: c.color }); setErrors({}); window.scrollTo({ top: 0, behavior: 'smooth' }); };

  const confirmDelete = async () => {
    setDeleting(true);
    try {
      await deleteCategory(toDelete.id);
      toast.success('Category deleted. Its tasks were kept.');
      if (editingId === toDelete.id) reset();
      setToDelete(null);
      await load();
    } catch (err) {
      toast.error(parseApiError(err).message);
    } finally {
      setDeleting(false);
    }
  };

  return (
    <>
      <div className="page-head"><h1>Categories</h1></div>

      <form className="card form row-form" onSubmit={handleSubmit} noValidate>
        <FormField label={editingId ? 'Edit category' : 'New category'} error={errors.name}>
          <input className="input" value={values.name} maxLength={50} placeholder="e.g. Work, Personal, Study"
            onChange={(e) => setValues((v) => ({ ...v, name: e.target.value }))} />
        </FormField>
        <FormField label="Colour" error={errors.color}>
          <input className="input color-input" type="color" value={values.color}
            onChange={(e) => setValues((v) => ({ ...v, color: e.target.value }))} />
        </FormField>
        <div className="row">
          <button className="btn btn-primary" disabled={submitting}>
            {submitting ? 'Saving…' : editingId ? 'Save changes' : 'Add category'}
          </button>
          {editingId && <button type="button" className="btn" onClick={reset}>Cancel</button>}
        </div>
      </form>

      {loading ? (
        <Loader />
      ) : categories.length === 0 ? (
        <div className="card empty"><p>No categories yet. Add one above to start organising your tasks.</p></div>
      ) : (
        <div className="stack">
          {categories.map((c) => (
            <div key={c.id} className="card row between cat-row">
              <span className="chip chip-lg" style={{ '--chip': c.color }}><i className="dot" /> {c.name}</span>
              <span className="muted small">{c.task_count} {c.task_count === 1 ? 'task' : 'tasks'}</span>
              <div className="row">
                <button className="btn btn-small" onClick={() => startEdit(c)}>Edit</button>
                <button className="btn btn-small btn-danger-outline" onClick={() => setToDelete(c)}>Delete</button>
              </div>
            </div>
          ))}
        </div>
      )}

      <ConfirmDialog
        open={Boolean(toDelete)}
        title="Delete this category?"
        message={toDelete ? `"${toDelete.name}" will be removed. Its ${toDelete.task_count} task(s) will stay, without a category.` : ''}
        busy={deleting}
        onConfirm={confirmDelete}
        onCancel={() => setToDelete(null)}
      />
    </>
  );
}
