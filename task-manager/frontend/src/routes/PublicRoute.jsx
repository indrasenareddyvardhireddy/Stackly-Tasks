import { Navigate, Outlet } from 'react-router-dom';
import { useAuth } from '../context/AuthContext.jsx';
import Loader from '../components/Loader.jsx';

// Login / Register: logged-in users are sent to the dashboard.
export default function PublicRoute() {
  const { user, loading } = useAuth();
  if (loading) return <Loader fullPage />;
  if (user) return <Navigate to="/dashboard" replace />;
  return <Outlet />;
}
