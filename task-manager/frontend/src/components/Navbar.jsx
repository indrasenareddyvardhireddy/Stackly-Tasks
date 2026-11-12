import { useState } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext.jsx';
import { useTheme } from '../context/ThemeContext.jsx';
import { useToast } from '../context/ToastContext.jsx';

export default function Navbar() {
  const { user, logout } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const toast = useToast();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);

  const handleLogout = async () => {
    await logout();
    toast.success('You have been logged out.');
    navigate('/login');
  };

  const links = [
    ['/dashboard', 'Dashboard'],
    ['/tasks', 'Tasks'],
    ['/categories', 'Categories'],
    ['/profile', 'Profile'],
  ];

  return (
    <header className="navbar">
      <div className="navbar-inner">
        <span className="brand">Taskboard</span>
        <button className="btn btn-ghost nav-toggle" onClick={() => setOpen((o) => !o)} aria-label="Menu">☰</button>
        <nav className={`nav-links ${open ? 'open' : ''}`} onClick={() => setOpen(false)}>
          {links.map(([to, label]) => (
            <NavLink key={to} to={to} className={({ isActive }) => (isActive ? 'active' : '')}>{label}</NavLink>
          ))}
        </nav>
        <div className={`nav-user ${open ? 'open' : ''}`}>
          <span className="nav-name">{user.first_name} {user.last_name}</span>
          <button className="btn btn-ghost" onClick={toggleTheme}>{theme === 'light' ? 'Dark mode' : 'Light mode'}</button>
          <button className="btn" onClick={handleLogout}>Logout</button>
        </div>
      </div>
    </header>
  );
}
