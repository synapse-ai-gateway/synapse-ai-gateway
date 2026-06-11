import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api, isMockEnabled, setMockEnabled } from '@/lib/api';
import { useAuth } from '@/context/AuthContext';
import type { DlpPattern, CreateDlpPatternRequest } from '@/lib/types';
import ConfirmDialog from '@/components/ConfirmDialog';
import TableSkeleton from '@/components/TableSkeleton';
import ModelSelect from '@/components/ModelSelect';
import { Plus, Trash2, ShieldCheck, AlertTriangle } from 'lucide-react';

const ROLE_RANK: Record<string, number> = { readonly: 0, analyst: 1, admin: 2, superadmin: 3 };
function hasRole(r: string, min: string) { return (ROLE_RANK[r] ?? 0) >= (ROLE_RANK[min] ?? 99); }

const WINDOW_OPTIONS = [
  { label: '1 minute', value: '60' },
  { label: '5 minutes', value: '300' },
  { label: '10 minutes', value: '600' },
  { label: '1 hour', value: '3600' },
];
const SEVERITIES = ['critical', 'high', 'medium', 'low'];

type Toast = { id: number; msg: string; type: 'success' | 'error' };

export default function SettingsPage() {
  const { user } = useAuth();
  const qc = useQueryClient();
  const isSuperadmin = user && hasRole(user.role, 'superadmin');

  const [toasts, setToasts] = useState<Toast[]>([]);
  const toast = (msg: string, type: 'success' | 'error' = 'success') => {
    const id = Date.now();
    setToasts(t => [...t, { id, msg, type }]);
    setTimeout(() => setToasts(t => t.filter(x => x.id !== id)), 4000);
  };

  const [mockMode, setMockMode] = useState(isMockEnabled());
  const [mockConfirmOpen, setMockConfirmOpen] = useState(false);

  const applyMockMode = (val: boolean) => {
    setMockEnabled(val);
    setMockMode(val);
    // Reload so all queries re-run against the right source
    window.location.reload();
  };

  const handleMockToggle = (val: boolean) => {
    if (val) {
      // Turning on — confirm first so people see the demo creds before they get logged out.
      setMockConfirmOpen(true);
    } else {
      applyMockMode(false);
    }
  };

  const { data: settings, isLoading: loadingSettings } = useQuery({ queryKey: ['settings'], queryFn: api.getSettings });
  const { data: patterns, isLoading: loadingPatterns } = useQuery({ queryKey: ['dlp-patterns'], queryFn: api.getDlpPatterns });

  // Gateway config form state
  const [gatewayForm, setGatewayForm] = useState({ vllm_url: '', default_model: '', timeout_sec: '' });
  const [rateForm, setRateForm] = useState({ default_requests: '', default_window_sec: '' });
  const [securityForm, setSecurityForm] = useState({
    max_failed_logins: '',
    lockout_minutes: '',
    min_password_age_days: '',
    max_password_age_days: '',
    password_history_count: '',
    inactivity_disable_days: '',
    access_token_expire_hours: '',
    session_warning_minutes: '',
    single_session_per_user: 'true',
  });

  useEffect(() => {
    if (settings) {
      setGatewayForm({ vllm_url: settings.vllm_url ?? '', default_model: settings.default_model ?? '', timeout_sec: settings.timeout_sec ?? '' });
      setRateForm({ default_requests: settings.default_requests ?? '', default_window_sec: settings.default_window_sec ?? '60' });
      setSecurityForm({
        max_failed_logins:       String(settings.max_failed_logins       ?? '5'),
        lockout_minutes:         String(settings.lockout_minutes          ?? '30'),
        min_password_age_days:   String(settings.min_password_age_days    ?? '1'),
        max_password_age_days:   String(settings.max_password_age_days    ?? '90'),
        password_history_count:  String(settings.password_history_count   ?? '24'),
        inactivity_disable_days: String(settings.inactivity_disable_days  ?? '90'),
        access_token_expire_hours: String(settings.access_token_expire_hours ?? '8'),
        session_warning_minutes: String(settings.session_warning_minutes  ?? '2'),
        single_session_per_user: String(settings.single_session_per_user  ?? 'true'),
      });
    }
  }, [settings]);

  const updateSettingsMut = useMutation({
    mutationFn: (data: object) => api.updateSettings(data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['settings'] }); toast('Settings saved.'); },
    onError: () => toast('Failed to save settings.', 'error'),
  });

  // DLP patterns
  const [deleteConfirm, setDeleteConfirm] = useState<DlpPattern | null>(null);
  const [addPatternOpen, setAddPatternOpen] = useState(false);
  const [newPattern, setNewPattern] = useState({ name: '', pattern: '', severity: 'medium', enabled: true });
  const [regexTestInput, setRegexTestInput] = useState('');
  const [regexTestResult, setRegexTestResult] = useState<string | null>(null);

  const deleteMut = useMutation({
    mutationFn: (name: string) => api.deleteDlpPattern(name),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['dlp-patterns'] }); toast('Pattern deleted.'); },
    onError: () => toast('Delete failed.', 'error'),
  });

  const updatePatternMut = useMutation({
    mutationFn: ({ name, data }: { name: string; data: object }) => api.updateDlpPattern(name, data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['dlp-patterns'] }); toast('Pattern updated.'); },
    onError: () => toast('Update failed.', 'error'),
  });

  const createPatternMut = useMutation({
    mutationFn: (data: CreateDlpPatternRequest) => api.createDlpPattern(data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['dlp-patterns'] }); toast('Pattern created.'); setAddPatternOpen(false); },
    onError: () => toast('Failed to create pattern.', 'error'),
  });

  const testRegex = () => {
    try {
      const re = new RegExp(newPattern.pattern, 'gi');
      const matches = regexTestInput.match(re);
      setRegexTestResult(matches ? `${matches.length} match(es): ${matches.slice(0, 5).join(', ')}` : 'No matches found.');
    } catch {
      setRegexTestResult('Invalid regex pattern.');
    }
  };

  if (loadingSettings) return <div className="p-6"><TableSkeleton cols={2} rows={4} /></div>;

  return (
    <div className="space-y-6 max-w-3xl">
      {/* Toasts */}
      <div className="fixed top-4 right-4 z-50 space-y-2">
        {toasts.map(t => (
          <div key={t.id} className={`px-4 py-2 rounded shadow text-sm text-white ${t.type === 'success' ? 'bg-green-600' : 'bg-red-600'}`}>{t.msg}</div>
        ))}
      </div>

      <h2 className="text-lg font-semibold text-gray-900">Settings</h2>

      {/* Gateway config */}
      <div className="bg-white border border-gray-200 rounded-lg p-6">
        <h3 className="text-sm font-semibold text-gray-900 mb-4">Gateway Configuration</h3>
        <div className="space-y-3">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">vLLM Endpoint URL</label>
            <input value={gatewayForm.vllm_url} onChange={e => setGatewayForm(f => ({ ...f, vllm_url: e.target.value }))}
              className="w-full px-3 py-2 border border-gray-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500" />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Default Model</label>
            <ModelSelect
              value={gatewayForm.default_model}
              onChange={v => setGatewayForm(f => ({ ...f, default_model: v }))}
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Request Timeout (seconds)</label>
            <input type="number" min={1} value={gatewayForm.timeout_sec} onChange={e => setGatewayForm(f => ({ ...f, timeout_sec: e.target.value }))}
              className="w-48 px-3 py-2 border border-gray-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500" />
          </div>
        </div>
        <button
          onClick={() => updateSettingsMut.mutate(gatewayForm)}
          disabled={updateSettingsMut.isPending}
          className="mt-4 px-4 py-2 text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 rounded disabled:opacity-60 flex items-center gap-2"
        >
          {updateSettingsMut.isPending && <span className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />}
          Save Gateway Config
        </button>
      </div>

      {/* Default rate limit */}
      <div className="bg-white border border-gray-200 rounded-lg p-6">
        <h3 className="text-sm font-semibold text-gray-900 mb-4">Default Rate Limit</h3>
        <p className="text-xs text-gray-500 mb-4">Applied to API keys not explicitly configured in the Teams table.</p>
        <div className="flex gap-4 items-end">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Requests</label>
            <input type="number" min={1} value={rateForm.default_requests} onChange={e => setRateForm(f => ({ ...f, default_requests: e.target.value }))}
              className="w-24 px-3 py-2 border border-gray-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500" />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Window</label>
            <select value={rateForm.default_window_sec} onChange={e => setRateForm(f => ({ ...f, default_window_sec: e.target.value }))}
              className="px-3 py-2 border border-gray-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500">
              {WINDOW_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
          </div>
          <button
            onClick={() => updateSettingsMut.mutate(rateForm)}
            disabled={updateSettingsMut.isPending}
            className="px-4 py-2 text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 rounded disabled:opacity-60"
          >
            Save
          </button>
        </div>
      </div>

      {/* Security Controls */}
      <div className="bg-white border border-gray-200 rounded-lg p-6">
        <div className="flex items-center gap-2 mb-1">
          <ShieldCheck className="w-4 h-4 text-indigo-600" />
          <h3 className="text-sm font-semibold text-gray-900">Security Controls</h3>
        </div>
        <p className="text-xs text-gray-500 mb-5">
          InfoSec baseline — password policy, account lockout, session management.
        </p>

        <div className="space-y-6">
          {/* Account Lockout */}
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-gray-400 mb-3">Account Lockout</p>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Max Failed Login Attempts</label>
                <input type="number" min={1} max={20}
                  value={securityForm.max_failed_logins}
                  onChange={e => setSecurityForm(f => ({ ...f, max_failed_logins: e.target.value }))}
                  className="w-full px-3 py-2 border border-gray-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500" />
                <p className="text-xs text-gray-400 mt-1">Lock account after this many consecutive failures.</p>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Lockout Duration (minutes)</label>
                <input type="number" min={1}
                  value={securityForm.lockout_minutes}
                  onChange={e => setSecurityForm(f => ({ ...f, lockout_minutes: e.target.value }))}
                  className="w-full px-3 py-2 border border-gray-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500" />
                <p className="text-xs text-gray-400 mt-1">Minutes the account stays locked before auto-unlock.</p>
              </div>
            </div>
          </div>

          {/* Password Policy */}
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-gray-400 mb-3">Password Policy</p>
            <div className="grid grid-cols-3 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Min Password Age (days)</label>
                <input type="number" min={0}
                  value={securityForm.min_password_age_days}
                  onChange={e => setSecurityForm(f => ({ ...f, min_password_age_days: e.target.value }))}
                  className="w-full px-3 py-2 border border-gray-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500" />
                <p className="text-xs text-gray-400 mt-1">Prevent cycling too quickly. Set 0 to disable.</p>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Max Password Age (days)</label>
                <input type="number" min={0}
                  value={securityForm.max_password_age_days}
                  onChange={e => setSecurityForm(f => ({ ...f, max_password_age_days: e.target.value }))}
                  className="w-full px-3 py-2 border border-gray-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500" />
                <p className="text-xs text-gray-400 mt-1">Force change after N days. Set 0 to disable.</p>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Password History Count</label>
                <input type="number" min={0}
                  value={securityForm.password_history_count}
                  onChange={e => setSecurityForm(f => ({ ...f, password_history_count: e.target.value }))}
                  className="w-full px-3 py-2 border border-gray-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500" />
                <p className="text-xs text-gray-400 mt-1">Reject reuse of last N passwords. Set 0 to disable.</p>
              </div>
            </div>
          </div>

          {/* Session / Inactivity */}
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-gray-400 mb-3">Session &amp; Inactivity</p>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Inactivity Auto-Disable (days)</label>
                <input type="number" min={0}
                  value={securityForm.inactivity_disable_days}
                  onChange={e => setSecurityForm(f => ({ ...f, inactivity_disable_days: e.target.value }))}
                  className="w-full px-3 py-2 border border-gray-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500" />
                <p className="text-xs text-gray-400 mt-1">Disable accounts with no login for N days. Set 0 to disable.</p>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Session Token Duration (hours)</label>
                <input type="number" min={1} max={24}
                  value={securityForm.access_token_expire_hours}
                  onChange={e => setSecurityForm(f => ({ ...f, access_token_expire_hours: e.target.value }))}
                  className="w-full px-3 py-2 border border-gray-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500" />
                <p className="text-xs text-gray-400 mt-1">JWT access token lifetime. Takes effect on next login.</p>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Session Warning (minutes before expiry)</label>
                <input type="number" min={1} max={60}
                  value={securityForm.session_warning_minutes}
                  onChange={e => setSecurityForm(f => ({ ...f, session_warning_minutes: e.target.value }))}
                  className="w-full px-3 py-2 border border-gray-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500" />
                <p className="text-xs text-gray-400 mt-1">Show "session expiring" dialog N minutes before logout.</p>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Single Session Per User</label>
                <button
                  onClick={() => setSecurityForm(f => ({ ...f, single_session_per_user: f.single_session_per_user === 'true' ? 'false' : 'true' }))}
                  className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none mt-1 ${securityForm.single_session_per_user === 'true' ? 'bg-emerald-500' : 'bg-gray-300'}`}
                >
                  <span className={`w-4 h-4 bg-white rounded-full shadow transition-transform ${securityForm.single_session_per_user === 'true' ? 'translate-x-6' : 'translate-x-1'}`} />
                </button>
                <p className="text-xs text-gray-400 mt-1">When enabled, a new login invalidates all previous sessions.</p>
              </div>
            </div>
          </div>
        </div>

        <button
          onClick={() => updateSettingsMut.mutate(securityForm)}
          disabled={updateSettingsMut.isPending}
          className="mt-5 px-4 py-2 text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 rounded disabled:opacity-60 flex items-center gap-2"
        >
          {updateSettingsMut.isPending && <span className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />}
          Save Security Controls
        </button>
      </div>

      {/* DLP Patterns */}
      <div className="bg-white border border-gray-200 rounded-lg p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold text-gray-900">DLP Patterns</h3>
          <button onClick={() => { setNewPattern({ name: '', pattern: '', severity: 'medium', enabled: true }); setRegexTestInput(''); setRegexTestResult(null); setAddPatternOpen(true); }}
            className="flex items-center gap-1.5 text-sm text-indigo-600 border border-indigo-500 hover:bg-indigo-50 px-3 py-1.5 rounded">
            <Plus className="w-4 h-4" /> Add Pattern
          </button>
        </div>

        {loadingPatterns ? <TableSkeleton cols={4} rows={6} /> : (
          <table className="w-full text-sm">
            <thead className="border-b border-gray-200">
              <tr>
                <th className="text-left py-2 font-medium text-gray-600">Name</th>
                <th className="text-left py-2 font-medium text-gray-600">Pattern</th>
                <th className="text-left py-2 font-medium text-gray-600">Severity</th>
                <th className="text-left py-2 font-medium text-gray-600">Enabled</th>
                {isSuperadmin && <th className="py-2 w-8" />}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {!patterns?.length ? (
                <tr><td colSpan={5} className="py-6 text-center text-gray-400">No DLP patterns</td></tr>
              ) : patterns.map((p: DlpPattern) => (
                <tr key={p.name}>
                  <td className="py-2.5 pr-4 font-mono text-xs font-medium text-gray-700">{p.name}</td>
                  <td className="py-2.5 pr-4">
                    <span className="font-mono text-xs text-gray-500 truncate block max-w-[220px]" title={p.pattern}>{p.pattern}</span>
                  </td>
                  <td className="py-2.5 pr-4">
                    <select value={p.severity}
                      onChange={e => updatePatternMut.mutate({ name: p.name, data: { severity: e.target.value } })}
                      className="border border-gray-200 rounded text-xs px-1.5 py-1 focus:outline-none focus:ring-1 focus:ring-indigo-500">
                      {SEVERITIES.map(s => <option key={s} value={s}>{s}</option>)}
                    </select>
                  </td>
                  <td className="py-2.5 pr-4">
                    <button onClick={() => updatePatternMut.mutate({ name: p.name, data: { enabled: !p.enabled } })}
                      className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${p.enabled ? 'bg-emerald-500' : 'bg-gray-300'}`}>
                      <span className={`w-3.5 h-3.5 bg-white rounded-full shadow transition-transform ${p.enabled ? 'translate-x-4' : 'translate-x-1'}`} />
                    </button>
                  </td>
                  {isSuperadmin && (
                    <td className="py-2.5">
                      <button onClick={() => setDeleteConfirm(p)} className="text-gray-300 hover:text-red-500 transition-colors">
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Mock data toggle — kept at the bottom because it disconnects the UI
          from the real backend. Putting it last reduces accidental flips. */}
      <div className={`border rounded-lg p-5 flex items-center justify-between ${mockMode ? 'bg-amber-50 border-amber-200' : 'bg-white border-gray-200'}`}>
        <div>
          <p className="text-sm font-semibold text-gray-900 flex items-center gap-2">
            Mock Data Mode
            {mockMode && (
              <span className="text-xs font-medium bg-amber-200 text-amber-800 px-2 py-0.5 rounded-full">Active</span>
            )}
          </p>
          <p className="text-xs text-gray-500 mt-0.5">
            {mockMode
              ? 'All data is simulated. Toggle off to reconnect to the real backend.'
              : 'For UI-only demos without a backend. The login changes to demo credentials when enabled.'}
          </p>
        </div>
        <button
          onClick={() => handleMockToggle(!mockMode)}
          className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none ${mockMode ? 'bg-amber-400' : 'bg-gray-300'}`}
        >
          <span className={`w-4 h-4 bg-white rounded-full shadow transition-transform ${mockMode ? 'translate-x-6' : 'translate-x-1'}`} />
        </button>
      </div>

      {/* Mock-mode enable confirmation — shows demo credentials so the user
          isn't locked out of the simulated login after the page reloads. */}
      {mockConfirmOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/40" onClick={() => setMockConfirmOpen(false)} />
          <div className="relative bg-white rounded-lg shadow-xl p-6 max-w-md w-full mx-4">
            <div className="flex items-start gap-3 mb-4">
              <div className="flex-shrink-0 w-10 h-10 rounded-full bg-amber-100 flex items-center justify-center">
                <AlertTriangle className="w-5 h-5 text-amber-600" />
              </div>
              <div>
                <h3 className="text-base font-semibold text-gray-900">Enable Mock Data Mode?</h3>
                <p className="text-sm text-gray-600 mt-1">
                  The UI will disconnect from the real backend and serve simulated data. You will be
                  signed out and your current credentials will <span className="font-semibold">not</span> work.
                </p>
              </div>
            </div>

            <div className="bg-gray-50 border border-gray-200 rounded p-3 mb-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-gray-500 mb-2">
                Demo login (only valid in mock mode)
              </p>
              <dl className="text-sm font-mono space-y-1">
                <div className="flex">
                  <dt className="w-24 text-gray-500">username</dt>
                  <dd className="text-gray-900">admin</dd>
                </div>
                <div className="flex">
                  <dt className="w-24 text-gray-500">password</dt>
                  <dd className="text-gray-900">password</dd>
                </div>
              </dl>
              <p className="text-xs text-gray-500 mt-2">
                To turn mock mode off later, sign in with the demo credentials and toggle it off here,
                or clear <code className="font-mono bg-white px-1 rounded border border-gray-200">sg_use_mock</code> from browser local storage.
              </p>
            </div>

            <div className="flex justify-end gap-3">
              <button
                onClick={() => setMockConfirmOpen(false)}
                className="px-4 py-2 text-sm text-gray-700 border border-gray-300 rounded hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                onClick={() => { setMockConfirmOpen(false); applyMockMode(true); }}
                className="px-4 py-2 text-sm font-medium text-white bg-amber-500 hover:bg-amber-600 rounded"
              >
                Enable mock mode
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Delete confirm */}
      <ConfirmDialog
        open={!!deleteConfirm}
        title="Delete DLP pattern?"
        description={<>Delete pattern <code className="font-mono bg-gray-100 px-1 rounded">{deleteConfirm?.name}</code>? This cannot be undone.</>}
        confirmLabel="Delete"
        confirmVariant="danger"
        onConfirm={() => { if (deleteConfirm) deleteMut.mutate(deleteConfirm.name); setDeleteConfirm(null); }}
        onCancel={() => setDeleteConfirm(null)}
      />

      {/* Add pattern dialog */}
      {addPatternOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/40" onClick={() => setAddPatternOpen(false)} />
          <div className="relative bg-white rounded-lg shadow-xl p-6 max-w-lg w-full mx-4">
            <h3 className="text-base font-semibold text-gray-900 mb-4">Add DLP Pattern</h3>
            <div className="space-y-3">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Name (unique identifier)</label>
                <input value={newPattern.name} onChange={e => setNewPattern(p => ({ ...p, name: e.target.value }))}
                  placeholder="e.g. passport_no"
                  className="w-full px-3 py-2 border border-gray-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Regex Pattern</label>
                <input value={newPattern.pattern} onChange={e => setNewPattern(p => ({ ...p, pattern: e.target.value }))}
                  placeholder="e.g. \b[A-Z]{2}\d{7}\b"
                  className="w-full px-3 py-2 border border-gray-300 rounded text-sm font-mono focus:outline-none focus:ring-2 focus:ring-indigo-500" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Severity</label>
                <select value={newPattern.severity} onChange={e => setNewPattern(p => ({ ...p, severity: e.target.value }))}
                  className="px-3 py-2 border border-gray-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500">
                  {SEVERITIES.map(s => <option key={s} value={s}>{s}</option>)}
                </select>
              </div>
              {/* Regex tester */}
              <div className="border border-gray-200 rounded p-3 bg-gray-50">
                <p className="text-xs font-medium text-gray-600 mb-2">Regex Tester</p>
                <textarea rows={3} value={regexTestInput} onChange={e => setRegexTestInput(e.target.value)}
                  placeholder="Paste sample text here to test the pattern…"
                  className="w-full px-2 py-1.5 border border-gray-300 rounded text-xs focus:outline-none resize-none mb-2" />
                <button onClick={testRegex} className="text-xs px-3 py-1.5 bg-gray-200 hover:bg-gray-300 rounded">Test</button>
                {regexTestResult && (
                  <p className={`mt-2 text-xs ${regexTestResult.includes('match') && !regexTestResult.includes('No') ? 'text-green-700' : regexTestResult.includes('Invalid') ? 'text-red-600' : 'text-gray-500'}`}>
                    {regexTestResult}
                  </p>
                )}
              </div>
            </div>
            <div className="mt-4 flex justify-end gap-3">
              <button onClick={() => setAddPatternOpen(false)} className="px-4 py-2 text-sm text-gray-700 border border-gray-300 rounded hover:bg-gray-50">Cancel</button>
              <button
                onClick={() => createPatternMut.mutate(newPattern)}
                disabled={createPatternMut.isPending || !newPattern.name || !newPattern.pattern}
                className="px-4 py-2 text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 rounded disabled:opacity-60 flex items-center gap-2"
              >
                {createPatternMut.isPending && <span className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />}
                Create Pattern
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
