import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import FormField from '../components/FormField.jsx';
import { useAuth } from '../context/AuthContext.jsx';
import { useToast } from '../context/ToastContext.jsx';
import { parseApiError } from '../utils/errors.js';

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export default function Login() {
  const { login } = useAuth();
  const toast = useToast();
  const navigate = useNavigate();
  const [values, setValues] = useState({ email: '', password: '' });
  const [errors, setErrors] = useState({});
  const [formError, setFormError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const set = (name) => (e) => setValues((v) => ({ ...v, [name]: e.target.value }));

  const handleSubmit = async (e) => {
    e.preventDefault();
    const errs = {};
    if (!values.email.trim()) errs.email = 'Email is required.';
    else if (!EMAIL_RE.test(values.email.trim())) errs.email = 'Enter a valid email address.';
    if (!values.password) errs.password = 'Password is required.';
    setErrors(errs);
    setFormError('');
    if (Object.keys(errs).length) return;

    setSubmitting(true);
    try {
      await login(values.email.trim().toLowerCase(), values.password);
      toast.success('Welcome back!');
      navigate('/dashboard', { replace: true });
    } catch (err) {
      const { message, fieldErrors } = parseApiError(err);
      setErrors(fieldErrors);
      setFormError(message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="auth-page">
      <form className="card auth-card" onSubmit={handleSubmit} noValidate>
        <h1>Log in</h1>
        <p className="muted">Pick up where you left off.</p>
        {formError && <div className="alert alert-error">{formError}</div>}
        <FormField label="Email" error={errors.email}>
          <input className="input" type="email" autoComplete="email" value={values.email} onChange={set('email')} />
        </FormField>
        <FormField label="Password" error={errors.password}>
          <input className="input" type="password" autoComplete="current-password" value={values.password} onChange={set('password')} />
        </FormField>
        <button className="btn btn-primary btn-block" disabled={submitting}>{submitting ? 'Logging in…' : 'Log in'}</button>
        <p className="muted small center">New here? <Link to="/register">Create an account</Link></p>
      </form>
    </div>
  );
}
