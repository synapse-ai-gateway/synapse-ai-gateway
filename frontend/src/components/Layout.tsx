import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import {
  LayoutDashboard, Users, Shield, FileText, Settings,
  Activity, LogOut, Cpu, ChevronRight, BookOpen
} from 'lucide-react';
import { useAuth } from '@/context/AuthContext';
import { useIsFetching } from '@tanstack/react-query';
import Logo from '@/components/Logo';

const navItems = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard, minRole: 'analyst' },
  { to: '/teams', label: 'Teams', icon: Cpu, minRole: 'analyst' },
  { to: '/dlp-incidents', label: 'DLP Incidents', icon: Shield, minRole: 'analyst' },
  { to: '/audit-log', label: 'Audit Log', icon: FileText, minRole: 'analyst' },
  { to: '/settings', label: 'Settings', icon: Settings, minRole: 'admin' },
  { to: '/users', label: 'Users', icon: Users, minRole: 'superadmin' },
  { to: '/activity-log', label: 'Activity Log', icon: Activity, minRole: 'superadmin' },
  { to: '/api-docs', label: 'API Docs', icon: BookOpen, minRole: 'readonly' },
];

const ROLE_RANK: Record<string, number> = {
  readonly: 0, analyst: 1, admin: 2, superadmin: 3,
};

function hasRole(userRole: string, minRole: string): boolean {
  return (ROLE_RANK[userRole] ?? 0) >= (ROLE_RANK[minRole] ?? 99);
}

const PAGE_TITLES: Record<string, string> = {
  '/': 'Dashboard',
  '/teams': 'Teams',
  '/dlp-incidents': 'DLP Incidents',
  '/audit-log': 'Audit Log',
  '/settings': 'Settings',
  '/users': 'Users',
  '/activity-log': 'Activity Log',
  '/api-docs': 'API Documentation',
};

export default function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const isFetching = useIsFetching();
  const currentPath = window.location.pathname;
  const pageTitle = PAGE_TITLES[currentPath] ?? 'Synapse AI Gateway';

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <div className="flex h-screen bg-[#F9FAFB] overflow-hidden">
      {/* Sidebar */}
      <aside className="w-60 flex-shrink-0 bg-slate-900 flex flex-col">
        {/* Header */}
        <div className="px-4 py-5 border-b border-white/10">
          <div className="flex items-center gap-2.5">
            <Logo className="w-6 h-6 text-white" />
            <span className="text-white font-semibold text-sm leading-tight">
              Synapse AI Gateway
            </span>
          </div>
          {user && (
            <p className="text-white/50 text-xs mt-2 truncate">{user.username} · {user.role}</p>
          )}
        </div>

        {/* Nav */}
        <nav className="flex-1 px-2 py-3 overflow-y-auto">
          {navItems
            .filter(item => user && hasRole(user.role, item.minRole))
            .map(({ to, label, icon: Icon }) => (
              <NavLink
                key={to}
                to={to}
                end={to === '/'}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-3 py-2 rounded text-sm mb-0.5 transition-colors ${
                    isActive
                      ? 'bg-white/20 text-white font-medium'
                      : 'text-white/70 hover:text-white hover:bg-white/10'
                  }`
                }
              >
                <Icon className="w-4 h-4 flex-shrink-0" />
                {label}
              </NavLink>
            ))}
        </nav>

        {/* Bottom */}
        <div className="px-2 py-3 border-t border-white/10 space-y-1">
          <button
            onClick={handleLogout}
            className="w-full flex items-center gap-3 px-3 py-2 rounded text-sm text-white/70 hover:text-white hover:bg-white/10 transition-colors"
          >
            <LogOut className="w-4 h-4" />
            Sign out
          </button>
        </div>
      </aside>

      {/* Main */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Top bar */}
        <header className="h-14 bg-white border-b border-gray-200 flex items-center px-6 gap-4 flex-shrink-0">
          <div className="flex items-center gap-2 text-gray-400 text-sm">
            <ChevronRight className="w-4 h-4" />
            <span className="text-gray-900 font-medium">{pageTitle}</span>
          </div>
          <div className="ml-auto flex items-center gap-3">
            {isFetching > 0 && (
              <div className="flex items-center gap-1.5 text-xs text-gray-500">
                <span className="w-3 h-3 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
                Loading…
              </div>
            )}
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 overflow-y-auto p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
