import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import FormField from '../components/FormField.jsx';
import { register } from '../api/authApi.js';
import { useToast } from '../context/ToastContext.jsx';
import { parseApiError } from '../utils/errors.js';

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export default function Register() {
  const toast = useToast();
  const navigate = useNavigate();
  const [values, setValues] = useState({ first_name: '', last_name: '', email: '', password: '', confirm_password: '' });
  const [errors, setErrors] = useState({});
  const [submitting, setSubmitting] = useState(false);

  const set = (name) => (e) => setValues((v) => ({ ...v, [name]: e.target.value }));

  const validate = () => {
    const errs = {};
    if (!values.first_name.trim()) errs.first_name = 'First name is required.';
    if (!values.last_name.trim()) errs.last_name = 'Last name is required.';
    if (!values.email.trim()) errs.email = 'Email is required.';
    else if (!EMAIL_RE.test(values.email.trim())) errs.email = 'Enter a valid email address.';
    if (!values.password) errs.password = 'Password is required.';
    else if (values.password.length < 8) errs.password = 'Password must be at least 8 characters.';
    if (!values.confirm_password) errs.confirm_password = 'Please confirm your password.';
    else if (values.password !== values.confirm_password) errs.confirm_password = 'Passwords do not match.';
    return errs;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    const errs = validate();
    setErrors(errs);
    if (Object.keys(errs).length) return;

    setSubmitting(true);
    try {
      await register({ ...values, email: values.email.trim().toLowerCase() });
      toast.success('Account created. Please log in.');
      navigate('/login');
    } catch (err) {
      const { message, fieldErrors } = parseApiError(err);
      setErrors(fieldErrors); // backend errors appear under the right fields
      toast.error(message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="auth-page">
      <form className="card auth-card" onSubmit={handleSubmit} noValidate>
        <h1>Create your account</h1>
        <div className="grid-2">
          <FormField label="First name" error={errors.first_name}>
            <input className="input" value={values.first_name} onChange={set('first_name')} autoComplete="given-name" />
          </FormField>
          <FormField label="Last name" error={errors.last_name}>
            <input className="input" value={values.last_name} onChange={set('last_name')} autoComplete="family-name" />
          </FormField>
        </div>
        <FormField label="Email" error={errors.email}>
          <input className="input" type="email" value={values.email} onChange={set('email')} autoComplete="email" />
        </FormField>
        <FormField label="Password" error={errors.password} hint="At least 8 characters.">
          <input className="input" type="password" value={values.password} onChange={set('password')} autoComplete="new-password" />
        </FormField>
        <FormField label="Confirm password" error={errors.confirm_password}>
          <input className="input" type="password" value={values.confirm_password} onChange={set('confirm_password')} autoComplete="new-password" />
        </FormField>
        <button className="btn btn-primary btn-block" disabled={submitting}>{submitting ? 'Creating account…' : 'Create account'}</button>
        <p className="muted small center">Already registered? <Link to="/login">Log in</Link></p>
      </form>
    </div>
  );
}
