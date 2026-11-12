import { Link } from 'react-router-dom';

export default function NotFound() {
  return (
    <div className="auth-page">
      <div className="card auth-card center">
        <h1>404</h1>
        <p className="muted">We couldn't find that page.</p>
        <Link className="btn btn-primary" to="/dashboard">Back to dashboard</Link>
      </div>
    </div>
  );
}
