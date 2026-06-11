import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '@/lib/api';
import { Check, X } from 'lucide-react';
import Logo from '@/components/Logo';

function checkStrength(pwd: string) {
  return {
    length: pwd.length >= 12,
    upper: /[A-Z]/.test(pwd),
    lower: /[a-z]/.test(pwd),
    number: /\d/.test(pwd),
    special: /[!@#$%^&*()\-_=+[\]{}|;:'",.<>?/`~\\]/.test(pwd),
  };
}

function strengthLabel(checks: ReturnType<typeof checkStrength>): { label: string; color: string } {
  const count = Object.values(checks).filter(Boolean).length;
  if (count <= 2) return { label: 'Weak', color: 'text-red-600' };
  if (count <= 4) return { label: 'Medium', color: 'text-amber-600' };
  return { label: 'Strong', color: 'text-green-600' };
}

export default function ChangePasswordPage() {
  const navigate = useNavigate();
  const [current, setCurrent] = useState('');
  const [next, setNext] = useState('');
  const [confirm, setConfirm] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const checks = checkStrength(next);
  const { label, color } = strengthLabel(checks);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (next !== confirm) { setError('Passwords do not match.'); return; }
    setError('');
    setLoading(true);
    try {
      await api.changePassword(current, next);
      navigate('/');
    } catch {
      setError('Failed to change password. Check your current password and try again.');
    } finally {
      setLoading(false);
    }
  };

  const Req = ({ met, text }: { met: boolean; text: string }) => (
    <div className={`flex items-center gap-1.5 text-xs ${met ? 'text-green-600' : 'text-gray-400'}`}>
      {met ? <Check className="w-3 h-3" /> : <X className="w-3 h-3" />}
      {text}
    </div>
  );

  return (
    <div className="min-h-screen bg-[#F9FAFB] flex items-center justify-center">
      <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-8 w-full max-w-sm">
        <div className="flex flex-col items-center mb-6">
          <Logo className="w-12 h-12 text-slate-900 mb-3" />
          <h1 className="text-xl font-semibold text-gray-900">Change Password</h1>
          <p className="text-xs text-gray-500 mt-1 text-center">You must change your password before continuing.</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Current password</label>
            <input type="password" value={current} onChange={e => setCurrent(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500" required />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">New password</label>
            <input type="password" value={next} onChange={e => setNext(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500" required />
            {next && (
              <div className="mt-2 space-y-1">
                <p className={`text-xs font-medium ${color}`}>Strength: {label}</p>
                <Req met={checks.length} text="At least 12 characters" />
                <Req met={checks.upper} text="Uppercase letter" />
                <Req met={checks.lower} text="Lowercase letter" />
                <Req met={checks.number} text="Number" />
                <Req met={checks.special} text="Special character" />
              </div>
            )}
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Confirm new password</label>
            <input type="password" value={confirm} onChange={e => setConfirm(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500" required />
          </div>

          {error && <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded px-3 py-2">{error}</div>}

          <button type="submit" disabled={loading}
            className="w-full bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium py-2 px-4 rounded-md disabled:opacity-60 flex items-center justify-center gap-2">
            {loading && <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />}
            Update password
          </button>
        </form>
      </div>
    </div>
  );
}
