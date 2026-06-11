import { Routes, Route, Navigate } from 'react-router-dom';
import { useAuth } from '@/context/AuthContext';
import Layout from '@/components/Layout';
import LoginPage from '@/pages/LoginPage';
import ChangePasswordPage from '@/pages/ChangePasswordPage';
import DashboardPage from '@/pages/DashboardPage';
import TeamsPage from '@/pages/TeamsPage';
import DlpIncidentsPage from '@/pages/DlpIncidentsPage';
import AuditLogPage from '@/pages/AuditLogPage';
import SettingsPage from '@/pages/SettingsPage';
import UsersPage from '@/pages/UsersPage';
import ActivityLogPage from '@/pages/ActivityLogPage';
import ApiDocsPage from '@/pages/ApiDocsPage';

function RequireAuth({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuth();
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

function RequireRole({ children, minRole }: { children: React.ReactNode; minRole: string }) {
  const { user } = useAuth();
  const ROLE_RANK: Record<string, number> = { readonly: 0, analyst: 1, admin: 2, superadmin: 3 };
  const has = user && (ROLE_RANK[user.role] ?? 0) >= (ROLE_RANK[minRole] ?? 99);
  if (!has) return <Navigate to="/" replace />;
  return <>{children}</>;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/change-password" element={<ChangePasswordPage />} />
      <Route
        path="/"
        element={
          <RequireAuth>
            <Layout />
          </RequireAuth>
        }
      >
        <Route index element={<DashboardPage />} />
        <Route path="teams" element={<TeamsPage />} />
        <Route path="dlp-incidents" element={<DlpIncidentsPage />} />
        <Route path="audit-log" element={<AuditLogPage />} />
        <Route path="settings" element={<RequireRole minRole="admin"><SettingsPage /></RequireRole>} />
        <Route path="users" element={<RequireRole minRole="superadmin"><UsersPage /></RequireRole>} />
        <Route path="activity-log" element={<RequireRole minRole="superadmin"><ActivityLogPage /></RequireRole>} />
      </Route>
      <Route path="/api-docs" element={<ApiDocsPage />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
