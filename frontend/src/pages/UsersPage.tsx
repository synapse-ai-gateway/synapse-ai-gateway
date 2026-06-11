import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import type { User, CreateUserRequest } from '@/lib/types';
import TableSkeleton from '@/components/TableSkeleton';
import ConfirmDialog from '@/components/ConfirmDialog';
import { formatDateTime } from '@/lib/utils';
import { Plus, Pencil, Key, Eye, EyeOff } from 'lucide-react';

const ROLES = ['superadmin', 'admin', 'analyst', 'readonly'] as const;
type RoleType = typeof ROLES[number];

const roleBadge: Record<string, string> = {
  superadmin: 'bg-purple-100 text-purple-800',
  admin: 'bg-blue-100 text-blue-800',
  analyst: 'bg-green-100 text-green-800',
  readonly: 'bg-gray-100 text-gray-700',
};

const ROLE_META: Record<RoleType, { label: string; color: string; perms: string[] }> = {
  superadmin: {
    label: 'Super Admin',
    color: 'border-purple-300 bg-purple-50',
    perms: ['Full system access', 'Manage all users & roles', 'All admin & analyst permissions'],
  },
  admin: {
    label: 'Admin',
    color: 'border-blue-300 bg-blue-50',
    perms: ['Manage teams & API keys', 'Manage DLP patterns', 'Edit gateway settings', 'View all logs & incidents'],
  },
  analyst: {
    label: 'Analyst',
    color: 'border-green-300 bg-green-50',
    perms: ['View DLP incidents & audit log', 'View activity log & stats', 'Read-only on teams & settings'],
  },
  readonly: {
    label: 'Read Only',
    color: 'border-gray-300 bg-gray-50',
    perms: ['View dashboard & summary stats', 'View team list (masked keys)', 'No access to logs or settings'],
  },
};

type Toast = { id: number; msg: string; type: 'success' | 'error' };

export default function UsersPage() {
  const qc = useQueryClient();

  const [toasts, setToasts] = useState<Toast[]>([]);
  const toast = (msg: string, type: 'success' | 'error' = 'success') => {
    const id = Date.now();
    setToasts(t => [...t, { id, msg, type }]);
    setTimeout(() => setToasts(t => t.filter(x => x.id !== id)), 4000);
  };

  const { data: users, isLoading } = useQuery({ queryKey: ['users'], queryFn: api.getUsers });

  // Create
  const [createOpen, setCreateOpen] = useState(false);
  const [newUser, setNewUser] = useState({ username: '', full_name: '', email: '', role: 'analyst' as RoleType, temp_password: '' });
  const [showTempPwd, setShowTempPwd] = useState(false);

  // Edit drawer
  const [editUser, setEditUser] = useState<User | null>(null);
  const [editData, setEditData] = useState({ full_name: '', email: '', role: 'analyst' as RoleType, enabled: true });

  // Reset password result
  const [resetResult, setResetResult] = useState<{ username: string; temp_password: string } | null>(null);

  // Role change confirm
  const [roleConfirm, setRoleConfirm] = useState<{ user: User; newRole: RoleType } | null>(null);

  // Disable confirm
  const [disableConfirm, setDisableConfirm] = useState<User | null>(null);

  const createMut = useMutation({
    mutationFn: (data: CreateUserRequest) => api.createUser(data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['users'] }); toast('User created.'); setCreateOpen(false); },
    onError: (e: Error) => toast(e.message ?? 'Failed to create user.', 'error'),
  });

  const updateMut = useMutation({
    mutationFn: ({ id, data }: { id: string; data: object }) => api.updateUser(id, data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['users'] }); toast('User updated.'); setEditUser(null); },
    onError: (e: Error) => toast(e.message ?? 'Update failed.', 'error'),
  });

  const resetPwdMut = useMutation({
    mutationFn: (id: string) => api.resetPassword(id),
    onSuccess: (res: { temp_password: string }, id: string) => {
      qc.invalidateQueries({ queryKey: ['users'] });
      const u = users?.find((u: User) => u.id === id);
      setResetResult({ username: u?.username ?? id, temp_password: res.temp_password });
    },
    onError: () => toast('Failed to reset password.', 'error'),
  });

  const openEdit = (u: User) => {
    setEditUser(u);
    setEditData({ full_name: u.full_name, email: u.email, role: u.role as RoleType, enabled: u.enabled });
  };

  const submitRoleChange = () => {
    if (roleConfirm) {
      updateMut.mutate({ id: roleConfirm.user.id, data: { role: roleConfirm.newRole } });
      setRoleConfirm(null);
    }
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
        <h2 className="text-lg font-semibold text-gray-900">Users</h2>
        <button onClick={() => { setNewUser({ username: '', full_name: '', email: '', role: 'analyst', temp_password: '' }); setShowTempPwd(false); setCreateOpen(true); }}
          className="flex items-center gap-1.5 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium px-3 py-1.5 rounded">
          <Plus className="w-4 h-4" /> Create User
        </button>
      </div>

      <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b border-gray-200">
            <tr>
              <th className="text-left px-4 py-3 font-medium text-gray-600">Username</th>
              <th className="text-left px-4 py-3 font-medium text-gray-600">Full Name</th>
              <th className="text-left px-4 py-3 font-medium text-gray-600">Email</th>
              <th className="text-left px-4 py-3 font-medium text-gray-600">Role</th>
              <th className="text-left px-4 py-3 font-medium text-gray-600">Status</th>
              <th className="text-left px-4 py-3 font-medium text-gray-600">Last Login</th>
              <th className="px-4 py-3" />
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {isLoading ? (
              <tr><td colSpan={7} className="px-4 py-6"><TableSkeleton cols={6} /></td></tr>
            ) : !users?.length ? (
              <tr><td colSpan={7} className="px-4 py-8 text-center text-gray-400">No users found</td></tr>
            ) : (
              users.map((u: User) => (
                <tr key={u.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 font-medium text-gray-900">{u.username}</td>
                  <td className="px-4 py-3 text-gray-700">{u.full_name}</td>
                  <td className="px-4 py-3 text-gray-500 text-xs">{u.email}</td>
                  <td className="px-4 py-3">
                    <span className={`text-xs font-medium px-2 py-0.5 rounded ${roleBadge[u.role] ?? 'bg-gray-100 text-gray-700'}`}>{u.role}</span>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`text-xs font-medium ${u.enabled ? 'text-green-700' : 'text-gray-400'}`}>{u.enabled ? 'Active' : 'Disabled'}</span>
                  </td>
                  <td className="px-4 py-3 text-gray-400 text-xs">{u.last_login ? formatDateTime(u.last_login) : '—'}</td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2 justify-end">
                      <button onClick={() => openEdit(u)} className="text-gray-400 hover:text-gray-700" title="Edit">
                        <Pencil className="w-3.5 h-3.5" />
                      </button>
                      <button onClick={() => resetPwdMut.mutate(u.id)} disabled={resetPwdMut.isPending} className="text-gray-400 hover:text-blue-600" title="Reset password">
                        <Key className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Role change confirm */}
      <ConfirmDialog
        open={!!roleConfirm}
        title="Change role?"
        description={`Change "${roleConfirm?.user.username}" role to "${roleConfirm?.newRole}"? This grants ${roleConfirm?.newRole === 'superadmin' ? 'full system access.' : 'elevated permissions.'}`}
        confirmLabel="Change Role"
        onConfirm={submitRoleChange}
        onCancel={() => setRoleConfirm(null)}
      />

      {/* Disable confirm */}
      <ConfirmDialog
        open={!!disableConfirm}
        title="Disable user?"
        description={`Disable "${disableConfirm?.username}"? Their active sessions will be invalidated immediately.`}
        confirmLabel="Disable"
        confirmVariant="danger"
        onConfirm={() => { if (disableConfirm) updateMut.mutate({ id: disableConfirm.id, data: { enabled: false } }); setDisableConfirm(null); }}
        onCancel={() => setDisableConfirm(null)}
      />

      {/* Create user dialog */}
      {createOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/40" onClick={() => setCreateOpen(false)} />
          <div className="relative bg-white rounded-lg shadow-xl w-full max-w-md mx-4 flex flex-col max-h-[90vh]">
            <div className="px-6 pt-6 pb-4 border-b border-gray-100 shrink-0">
              <h3 className="text-base font-semibold text-gray-900">Create User</h3>
            </div>
            <div className="overflow-y-auto flex-1 px-6 py-4">
            <div className="space-y-3">
              {(['username', 'full_name', 'email'] as const).map(f => (
                <div key={f}>
                  <label className="block text-sm font-medium text-gray-700 mb-1 capitalize">{f.replace('_', ' ')}</label>
                  <input value={newUser[f]} onChange={e => setNewUser(u => ({ ...u, [f]: e.target.value }))}
                    className="w-full px-3 py-2 border border-gray-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500" />
                </div>
              ))}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">Role</label>
                <div className="space-y-2">
                  {ROLES.map(r => {
                    const meta = ROLE_META[r];
                    const selected = newUser.role === r;
                    return (
                      <button
                        key={r}
                        type="button"
                        onClick={() => setNewUser(u => ({ ...u, role: r }))}
                        className={`w-full text-left px-3 py-2.5 rounded border-2 transition-colors ${selected ? meta.color + ' ' + 'border-opacity-100' : 'border-gray-200 bg-white hover:bg-gray-50'}`}
                      >
                        <div className="flex items-center gap-2 mb-1">
                          <span className={`text-xs font-semibold px-1.5 py-0.5 rounded ${roleBadge[r]}`}>{meta.label}</span>
                          {selected && <span className="ml-auto text-[10px] text-gray-500 font-medium">Selected</span>}
                        </div>
                        <ul className="space-y-0.5">
                          {meta.perms.map(p => (
                            <li key={p} className="text-xs text-gray-500 flex items-start gap-1.5">
                              <span className="mt-0.5 text-gray-400">·</span>{p}
                            </li>
                          ))}
                        </ul>
                      </button>
                    );
                  })}
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Temporary Password</label>
                <div className="relative">
                  <input type={showTempPwd ? 'text' : 'password'} value={newUser.temp_password} onChange={e => setNewUser(u => ({ ...u, temp_password: e.target.value }))}
                    className="w-full px-3 py-2 pr-9 border border-gray-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500" />
                  <button type="button" onClick={() => setShowTempPwd(v => !v)} className="absolute right-2.5 top-2.5 text-gray-400">
                    {showTempPwd ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>
            </div>
            </div>
            <div className="px-6 py-4 border-t border-gray-100 flex justify-end gap-3 shrink-0">
              <button onClick={() => setCreateOpen(false)} className="px-4 py-2 text-sm text-gray-700 border border-gray-300 rounded hover:bg-gray-50">Cancel</button>
              <button
                onClick={() => createMut.mutate({ ...newUser })}
                disabled={createMut.isPending || !newUser.username || !newUser.email || !newUser.temp_password}
                className="px-4 py-2 text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 rounded disabled:opacity-60 flex items-center gap-2"
              >
                {createMut.isPending && <span className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />}
                Create
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Edit drawer */}
      {editUser && (
        <div className="fixed inset-0 z-40 flex">
          <div className="flex-1 bg-black/30" onClick={() => setEditUser(null)} />
          <div className="w-[380px] bg-white h-full shadow-xl flex flex-col">
            <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
              <h3 className="font-semibold text-gray-900">Edit User — {editUser.username}</h3>
              <button onClick={() => setEditUser(null)} className="text-gray-400 text-xl leading-none">×</button>
            </div>
            <div className="flex-1 p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Full Name</label>
                <input value={editData.full_name} onChange={e => setEditData(d => ({ ...d, full_name: e.target.value }))}
                  className="w-full px-3 py-2 border border-gray-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
                <input value={editData.email} onChange={e => setEditData(d => ({ ...d, email: e.target.value }))}
                  className="w-full px-3 py-2 border border-gray-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">Role</label>
                <div className="space-y-2">
                  {ROLES.map(r => {
                    const meta = ROLE_META[r];
                    const selected = editData.role === r;
                    return (
                      <button
                        key={r}
                        type="button"
                        onClick={() => {
                          const newRole = r;
                          if (newRole === 'superadmin' || editUser.role === 'superadmin') {
                            setRoleConfirm({ user: editUser, newRole });
                          } else {
                            setEditData(d => ({ ...d, role: newRole }));
                          }
                        }}
                        className={`w-full text-left px-3 py-2.5 rounded border-2 transition-colors ${selected ? meta.color + ' border-opacity-100' : 'border-gray-200 bg-white hover:bg-gray-50'}`}
                      >
                        <div className="flex items-center gap-2 mb-1">
                          <span className={`text-xs font-semibold px-1.5 py-0.5 rounded ${roleBadge[r]}`}>{meta.label}</span>
                          {selected && <span className="ml-auto text-[10px] text-gray-500 font-medium">Selected</span>}
                        </div>
                        <ul className="space-y-0.5">
                          {meta.perms.map(p => (
                            <li key={p} className="text-xs text-gray-500 flex items-start gap-1.5">
                              <span className="mt-0.5 text-gray-400">·</span>{p}
                            </li>
                          ))}
                        </ul>
                      </button>
                    );
                  })}
                </div>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium text-gray-700">Enabled</span>
                <button
                  onClick={() => {
                    if (editData.enabled) setDisableConfirm(editUser);
                    else setEditData(d => ({ ...d, enabled: true }));
                  }}
                  className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${editData.enabled ? 'bg-emerald-500' : 'bg-gray-300'}`}
                >
                  <span className={`w-3.5 h-3.5 bg-white rounded-full shadow transition-transform ${editData.enabled ? 'translate-x-4' : 'translate-x-1'}`} />
                </button>
              </div>
            </div>
            <div className="px-6 py-4 border-t border-gray-200 flex justify-end gap-3">
              <button onClick={() => setEditUser(null)} className="px-4 py-2 text-sm text-gray-700 border border-gray-300 rounded hover:bg-gray-50">Cancel</button>
              <button
                onClick={() => updateMut.mutate({ id: editUser.id, data: editData })}
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

      {/* Reset password result */}
      {resetResult && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/40" />
          <div className="relative bg-white rounded-lg shadow-xl p-6 max-w-sm w-full mx-4">
            <h3 className="text-base font-semibold text-gray-900 mb-2">Password Reset</h3>
            <p className="text-sm text-gray-600 mb-3">Temporary password for <strong>{resetResult.username}</strong>. This will be shown only once.</p>
            <div className="bg-gray-100 rounded p-3 font-mono text-sm mb-3 select-all">{resetResult.temp_password}</div>
            <div className="flex gap-2 mb-4">
              <button onClick={() => navigator.clipboard.writeText(resetResult.temp_password)}
                className="flex-1 py-2 border border-gray-300 rounded text-sm hover:bg-gray-50">Copy</button>
            </div>
            <button onClick={() => setResetResult(null)} className="w-full py-2 bg-indigo-600 text-white text-sm rounded">Done</button>
          </div>
        </div>
      )}
    </div>
  );
}
