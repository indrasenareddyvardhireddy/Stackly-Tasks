import { useState } from 'react';
import FormField from '../components/FormField.jsx';
import { changePassword } from '../api/authApi.js';
import { useAuth } from '../context/AuthContext.jsx';
import { useToast } from '../context/ToastContext.jsx';
import { parseApiError } from '../utils/errors.js';

const BLANK = { old_password: '', new_password: '', confirm_password: '' };

export default function Profile() {
  const { user } = useAuth();
  const toast = useToast();
  const [values, setValues] = useState(BLANK);
  const [errors, setErrors] = useState({});
  const [submitting, setSubmitting] = useState(false);

  const set = (name) => (e) => setValues((v) => ({ ...v, [name]: e.target.value }));

  const handleSubmit = async (e) => {
    e.preventDefault();
    const errs = {};
    if (!values.old_password) errs.old_password = 'Enter your current password.';
    if (!values.new_password) errs.new_password = 'Enter a new password.';
    else if (values.new_password.length < 8) errs.new_password = 'Password must be at least 8 characters.';
    if (values.new_password !== values.confirm_password) errs.confirm_password = 'Passwords do not match.';
    setErrors(errs);
    if (Object.keys(errs).length) return;

    setSubmitting(true);
    try {
      await changePassword(values);
      toast.success('Password changed.');
      setValues(BLANK);
    } catch (err) {
      const { message, fieldErrors } = parseApiError(err);
      setErrors(fieldErrors);
      toast.error(message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <>
      <div className="page-head"><h1>Profile</h1></div>
      <section className="card">
        <dl className="details">
          <dt>Name</dt><dd>{user.first_name} {user.last_name}</dd>
          <dt>Email</dt><dd>{user.email}</dd>
          <dt>Member since</dt><dd>{new Date(user.date_joined).toLocaleDateString()}</dd>
        </dl>
      </section>

      <form className="card form" onSubmit={handleSubmit} noValidate>
        <h3>Change password</h3>
        <FormField label="Current password" error={errors.old_password}>
          <input className="input" type="password" autoComplete="current-password" value={values.old_password} onChange={set('old_password')} />
        </FormField>
        <FormField label="New password" error={errors.new_password} hint="At least 8 characters.">
          <input className="input" type="password" autoComplete="new-password" value={values.new_password} onChange={set('new_password')} />
        </FormField>
        <FormField label="Confirm new password" error={errors.confirm_password}>
          <input className="input" type="password" autoComplete="new-password" value={values.confirm_password} onChange={set('confirm_password')} />
        </FormField>
        <div className="row end">
          <button className="btn btn-primary" disabled={submitting}>{submitting ? 'Saving…' : 'Change password'}</button>
        </div>
      </form>
    </>
  );
}
