import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '@/context/AuthContext';
import Logo from '@/components/Logo';

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [lockoutMsg, setLockoutMsg] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLockoutMsg('');
    setLoading(true);
    try {
      const result = await login(username, password);
      if (result?.force_password_change) {
        navigate('/change-password');
      } else {
        navigate('/');
      }
    } catch (err: unknown) {
      const e = err as { status?: number; retry_after?: number; message?: string; detail?: unknown };
      if (e?.status === 423) {
        const detail = e.detail as { retry_after?: number } | undefined;
        const seconds = detail?.retry_after ?? e.retry_after ?? 900;
        const mins = Math.ceil(seconds / 60);
        setLockoutMsg(`Account locked. Try again in ${mins} minute${mins !== 1 ? 's' : ''}.`);
      } else if (e?.status === 401) {
        setError('Invalid username or password.');
      } else {
        setError(typeof e?.message === 'string' ? e.message : 'Unable to connect to the server. Is the backend running?');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#F9FAFB] flex items-center justify-center">
      <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-8 w-full max-w-sm">
        <div className="flex flex-col items-center mb-8">
          <Logo className="w-12 h-12 text-slate-900 mb-3" />
          <h1 className="text-xl font-semibold text-gray-900">Synapse AI Gateway</h1>
          <p className="text-sm text-gray-500 mt-1">Admin Console</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Username</label>
            <input
              type="text"
              value={username}
              onChange={e => setUsername(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
              required
              autoFocus
              autoComplete="username"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Password</label>
            <input
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
              required
              autoComplete="current-password"
            />
          </div>

          {error && (
            <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded px-3 py-2">
              {error}
            </div>
          )}
          {lockoutMsg && (
            <div className="text-sm text-orange-700 bg-orange-50 border border-orange-200 rounded px-3 py-2">
              {lockoutMsg}
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium py-2 px-4 rounded-md disabled:opacity-60 flex items-center justify-center gap-2"
          >
            {loading && <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />}
            Sign in
          </button>
        </form>
      </div>
    </div>
  );
}
