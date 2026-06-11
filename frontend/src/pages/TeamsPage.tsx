import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { useAuth } from '@/context/AuthContext';
import { maskApiKey, copyToClipboard } from '@/lib/utils';
import type { Team, CreateTeamRequest } from '@/lib/types';
import SeverityBadge from '@/components/SeverityBadge';
import ConfirmDialog from '@/components/ConfirmDialog';
import TableSkeleton from '@/components/TableSkeleton';
import ModelSelect from '@/components/ModelSelect';
import { Copy, Plus, Pencil, Check, Loader2 } from 'lucide-react';

const ROLE_RANK: Record<string, number> = { readonly: 0, analyst: 1, admin: 2, superadmin: 3 };
function hasRole(userRole: string, min: string) { return (ROLE_RANK[userRole] ?? 0) >= (ROLE_RANK[min] ?? 99); }

const WINDOW_OPTIONS = [
  { label: '1 minute', value: 60 },
  { label: '5 minutes', value: 300 },
  { label: '10 minutes', value: 600 },
  { label: '1 hour', value: 3600 },
];

function windowLabel(sec: number) {
  return WINDOW_OPTIONS.find(o => o.value === sec)?.label ?? `${sec}s`;
}

function generateUUID() {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
    const r = Math.random() * 16 | 0;
    return (c === 'x' ? r : (r & 0x3 | 0x8)).toString(16);
  });
}

type Toast = { id: number; msg: string; type: 'success' | 'error' };

export default function TeamsPage() {
  const { user } = useAuth();
  const qc = useQueryClient();
  const canEdit = user && hasRole(user.role, 'admin');

  const [toasts, setToasts] = useState<Toast[]>([]);
  const toast = (msg: string, type: 'success' | 'error' = 'success') => {
    const id = Date.now();
    setToasts(t => [...t, { id, msg, type }]);
    setTimeout(() => setToasts(t => t.filter(x => x.id !== id)), 4000);
  };

  // Drawer state
  const [drawerTeam, setDrawerTeam] = useState<Team | null>(null);
  const [drawerData, setDrawerData] = useState({ team_name: '', model: '', requests: 10, window_sec: 60, system_prompt: '', enabled: true });
  const [customWindow, setCustomWindow] = useState(false);

  // Add dialog state
  const [addOpen, setAddOpen] = useState(false);
  const [newTeam, setNewTeam] = useState({ api_key: '', team_name: '', model: '', requests: 10, window_sec: 60, system_prompt: '', enabled: true });
  const [createdKey, setCreatedKey] = useState<string | null>(null);
  const [keyCopied, setKeyCopied] = useState(false);

  // Per-row copy state: teamId → 'idle' | 'loading' | 'copied'
  const [copyState, setCopyState] = useState<Record<number, 'idle' | 'loading' | 'copied'>>({});

  const copyApiKey = async (teamId: number) => {
    setCopyState(s => ({ ...s, [teamId]: 'loading' }));
    try {
      const key = await api.getTeamApiKey(teamId);
      await copyToClipboard(key);
      setCopyState(s => ({ ...s, [teamId]: 'copied' }));
      setTimeout(() => setCopyState(s => ({ ...s, [teamId]: 'idle' })), 3000);
    } catch {
      toast('Failed to retrieve API key.', 'error');
      setCopyState(s => ({ ...s, [teamId]: 'idle' }));
    }
  };

  // Disable confirm
  const [confirmDisable, setConfirmDisable] = useState<Team | null>(null);

  const { data: teams, isLoading } = useQuery({ queryKey: ['teams'], queryFn: api.getTeams });

  const updateMut = useMutation({
    mutationFn: ({ id, data }: { id: number; data: object }) => api.updateTeam(id, data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['teams'] }); toast('Team updated.'); setDrawerTeam(null); },
    onError: () => toast('Update failed.', 'error'),
  });

  const createMut = useMutation({
    mutationFn: (data: CreateTeamRequest) => api.createTeam(data),
    onSuccess: (res: Team & { api_key: string }) => {
      qc.invalidateQueries({ queryKey: ['teams'] });
      setCreatedKey(res.api_key);
    },
    onError: () => toast('Failed to create team.', 'error'),
  });

  const openEdit = (team: Team) => {
    setDrawerTeam(team);
    setDrawerData({ team_name: team.team_name, model: team.model, requests: team.requests, window_sec: team.window_sec, system_prompt: team.system_prompt ?? '', enabled: team.enabled });
    setCustomWindow(!WINDOW_OPTIONS.some(o => o.value === team.window_sec));
  };

  const openAdd = () => {
    setNewTeam({ api_key: generateUUID(), team_name: '', model: '', requests: 10, window_sec: 60, system_prompt: '', enabled: true });
    setCreatedKey(null);
    setKeyCopied(false);
    setAddOpen(true);
  };

  const copyKey = async (key: string) => {
    await copyToClipboard(key);
    setKeyCopied(true);
  };

  return (
    <div className="space-y-4">
      {/* Toasts */}
      <div className="fixed top-4 right-4 z-50 space-y-2">
        {toasts.map(t => (
          <div key={t.id} className={`px-4 py-2 rounded shadow text-sm text-white ${t.type === 'success' ? 'bg-green-600' : 'bg-red-600'}`}>{t.msg}</div>
        ))}
      </div>

      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-900">Teams</h2>
        {canEdit && (
          <button onClick={openAdd} className="flex items-center gap-1.5 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium px-3 py-1.5 rounded">
            <Plus className="w-4 h-4" /> Add Team
          </button>
        )}
      </div>

      <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b border-gray-200">
            <tr>
              <th className="text-left px-4 py-3 font-medium text-gray-600">Team</th>
              <th className="text-left px-4 py-3 font-medium text-gray-600">API Key</th>
              <th className="text-left px-4 py-3 font-medium text-gray-600">Model</th>
              <th className="text-left px-4 py-3 font-medium text-gray-600">Rate Limit</th>
              <th className="text-left px-4 py-3 font-medium text-gray-600">Status</th>
              {canEdit && <th className="px-4 py-3" />}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {isLoading ? (
              <tr><td colSpan={canEdit ? 6 : 5} className="px-4 py-6"><TableSkeleton /></td></tr>
            ) : !teams?.length ? (
              <tr><td colSpan={canEdit ? 6 : 5} className="px-4 py-8 text-center text-gray-400">No teams configured</td></tr>
            ) : (
              teams.map((team: Team) => (
                <tr key={team.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 font-medium text-gray-900">{team.team_name}</td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-xs text-gray-400">
                        {maskApiKey(team.api_key)}
                      </span>
                      {canEdit && (
                        <button
                          onClick={() => copyApiKey(team.id)}
                          disabled={copyState[team.id] === 'loading'}
                          title="Copy full API key"
                          className="text-gray-300 hover:text-gray-600 transition-colors disabled:cursor-wait"
                        >
                          {copyState[team.id] === 'loading' ? (
                            <Loader2 className="w-3.5 h-3.5 animate-spin" />
                          ) : copyState[team.id] === 'copied' ? (
                            <Check className="w-3.5 h-3.5 text-green-500" />
                          ) : (
                            <Copy className="w-3.5 h-3.5" />
                          )}
                        </button>
                      )}
                    </div>
                  </td>
                  <td className="px-4 py-3 text-gray-600 font-mono text-xs">{team.model || '—'}</td>
                  <td className="px-4 py-3 text-gray-600">{team.requests} req / {windowLabel(team.window_sec)}</td>
                  <td className="px-4 py-3">
                    {canEdit ? (
                      <button
                        onClick={() => setConfirmDisable(team)}
                        className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${team.enabled ? 'bg-emerald-500' : 'bg-gray-300'}`}
                      >
                        <span className={`w-3.5 h-3.5 bg-white rounded-full shadow transition-transform ${team.enabled ? 'translate-x-4' : 'translate-x-1'}`} />
                      </button>
                    ) : (
                      <SeverityBadge severity={team.enabled ? 'low' : 'medium'} />
                    )}
                  </td>
                  {canEdit && (
                    <td className="px-4 py-3 text-right">
                      <button onClick={() => openEdit(team)} className="text-gray-400 hover:text-gray-700">
                        <Pencil className="w-4 h-4" />
                      </button>
                    </td>
                  )}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Disable confirm */}
      <ConfirmDialog
        open={!!confirmDisable}
        title={confirmDisable?.enabled ? 'Disable team?' : 'Enable team?'}
        description={`This will ${confirmDisable?.enabled ? 'disable' : 'enable'} the API key for "${confirmDisable?.team_name}".`}
        confirmLabel={confirmDisable?.enabled ? 'Disable' : 'Enable'}
        confirmVariant={confirmDisable?.enabled ? 'danger' : 'default'}
        onConfirm={() => {
          if (confirmDisable) updateMut.mutate({ id: confirmDisable.id, data: { enabled: !confirmDisable.enabled } });
          setConfirmDisable(null);
        }}
        onCancel={() => setConfirmDisable(null)}
      />

      {/* Edit Drawer */}
      {drawerTeam && (
        <div className="fixed inset-0 z-40 flex">
          <div className="flex-1 bg-black/30" onClick={() => setDrawerTeam(null)} />
          <div className="w-[420px] bg-white h-full shadow-xl flex flex-col">
            <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
              <h3 className="font-semibold text-gray-900">Edit Team</h3>
              <button onClick={() => setDrawerTeam(null)} className="text-gray-400 hover:text-gray-600 text-xl leading-none">×</button>
            </div>
            <div className="flex-1 overflow-y-auto p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Team Name</label>
                <input
                  value={drawerData.team_name}
                  onChange={e => setDrawerData(d => ({ ...d, team_name: e.target.value }))}
                  className="w-full px-3 py-2 border border-gray-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Model</label>
                <ModelSelect
                  value={drawerData.model}
                  onChange={v => setDrawerData(d => ({ ...d, model: v }))}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Rate Limit (requests)</label>
                <input type="number" min={1} value={drawerData.requests}
                  onChange={e => setDrawerData(d => ({ ...d, requests: parseInt(e.target.value) || 10 }))}
                  className="w-full px-3 py-2 border border-gray-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Window Duration</label>
                <select value={customWindow ? 'custom' : drawerData.window_sec}
                  onChange={e => {
                    if (e.target.value === 'custom') { setCustomWindow(true); }
                    else { setCustomWindow(false); setDrawerData(d => ({ ...d, window_sec: parseInt(e.target.value) })); }
                  }}
                  className="w-full px-3 py-2 border border-gray-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500">
                  {WINDOW_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                  <option value="custom">Custom</option>
                </select>
                {customWindow && (
                  <input type="number" min={1} value={drawerData.window_sec}
                    onChange={e => setDrawerData(d => ({ ...d, window_sec: parseInt(e.target.value) || 60 }))}
                    placeholder="Seconds"
                    className="mt-2 w-full px-3 py-2 border border-gray-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500" />
                )}
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">System Prompt</label>
                <textarea rows={5} value={drawerData.system_prompt}
                  onChange={e => setDrawerData(d => ({ ...d, system_prompt: e.target.value }))}
                  className="w-full px-3 py-2 border border-gray-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-none" />
              </div>
            </div>
            <div className="px-6 py-4 border-t border-gray-200 flex justify-end gap-3">
              <button onClick={() => setDrawerTeam(null)} className="px-4 py-2 text-sm text-gray-700 border border-gray-300 rounded hover:bg-gray-50">Cancel</button>
              <button
                onClick={() => updateMut.mutate({ id: drawerTeam.id, data: drawerData })}
                disabled={updateMut.isPending}
                className="px-4 py-2 text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 rounded disabled:opacity-60 flex items-center gap-2"
              >
                {updateMut.isPending && <span className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />}
                Save
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Add Team Dialog */}
      {addOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/40" />
          <div className="relative bg-white rounded-lg shadow-xl p-6 max-w-md w-full mx-4 max-h-[90vh] overflow-y-auto">
            {createdKey ? (
              <>
                <h3 className="text-base font-semibold text-gray-900 mb-3">Team Created</h3>
                <p className="text-sm text-amber-700 bg-amber-50 border border-amber-200 rounded p-3 mb-4">
                  This API key will not be shown again. Copy it now.
                </p>
                <div className="bg-gray-100 rounded p-3 font-mono text-sm break-all mb-4">{createdKey}</div>
                <button onClick={() => copyKey(createdKey)} className="w-full flex items-center justify-center gap-2 py-2 border border-gray-300 rounded text-sm hover:bg-gray-50 mb-4">
                  {keyCopied ? <><Check className="w-4 h-4 text-green-600" /> Copied!</> : <><Copy className="w-4 h-4" /> Copy API Key</>}
                </button>
                <button
                  disabled={!keyCopied}
                  onClick={() => { setAddOpen(false); toast('Team created successfully.'); }}
                  className="w-full py-2 bg-indigo-600 text-white text-sm rounded disabled:opacity-40"
                >
                  I have copied the key — Done
                </button>
              </>
            ) : (
              <>
                <h3 className="text-base font-semibold text-gray-900 mb-4">Add Team</h3>
                <div className="space-y-3">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Team Name</label>
                    <input value={newTeam.team_name} onChange={e => setNewTeam(d => ({ ...d, team_name: e.target.value }))}
                      className="w-full px-3 py-2 border border-gray-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500" />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Model</label>
                    <ModelSelect
                      value={newTeam.model}
                      onChange={v => setNewTeam(d => ({ ...d, model: v }))}
                    />
                  </div>
                  <div className="flex gap-3">
                    <div className="flex-1">
                      <label className="block text-sm font-medium text-gray-700 mb-1">Requests</label>
                      <input type="number" min={1} value={newTeam.requests} onChange={e => setNewTeam(d => ({ ...d, requests: parseInt(e.target.value) || 10 }))}
                        className="w-full px-3 py-2 border border-gray-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500" />
                    </div>
                    <div className="flex-1">
                      <label className="block text-sm font-medium text-gray-700 mb-1">Window</label>
                      <select value={newTeam.window_sec} onChange={e => setNewTeam(d => ({ ...d, window_sec: parseInt(e.target.value) }))}
                        className="w-full px-3 py-2 border border-gray-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500">
                        {WINDOW_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                      </select>
                    </div>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">System Prompt (optional)</label>
                    <textarea rows={3} value={newTeam.system_prompt} onChange={e => setNewTeam(d => ({ ...d, system_prompt: e.target.value }))}
                      className="w-full px-3 py-2 border border-gray-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-none" />
                  </div>
                </div>
                <div className="mt-4 flex justify-end gap-3">
                  <button onClick={() => setAddOpen(false)} className="px-4 py-2 text-sm text-gray-700 border border-gray-300 rounded hover:bg-gray-50">Cancel</button>
                  <button
                    onClick={() => createMut.mutate(newTeam)}
                    disabled={createMut.isPending || !newTeam.team_name}
                    className="px-4 py-2 text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 rounded disabled:opacity-60 flex items-center gap-2"
                  >
                    {createMut.isPending && <span className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />}
                    Create
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
