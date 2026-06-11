import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { api } from '@/lib/api';
import type { AuditLog } from '@/lib/types';
import StatusBadge from '@/components/StatusBadge';
import TableSkeleton from '@/components/TableSkeleton';
import { formatDateTime } from '@/lib/utils';
import { Download, ChevronDown, ChevronUp, AlertTriangle } from 'lucide-react';

const STATUSES = ['success', 'blocked_dlp', 'blocked_rate_limit', 'blocked_auth', 'error'];

export default function AuditLogPage() {
  const navigate = useNavigate();
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [teamName, setTeamName] = useState('');
  const [selectedStatuses, setSelectedStatuses] = useState<string[]>([]);
  const [page, setPage] = useState(1);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const filters = {
    start_date: startDate || undefined,
    end_date: endDate || undefined,
    team_name: teamName || undefined,
    statuses: selectedStatuses.length ? selectedStatuses : undefined,
    page,
    page_size: 20,
  };

  const { data, isLoading } = useQuery({
    queryKey: ['audit-log', filters],
    queryFn: () => api.getAuditLog(filters),
  });

  const toggleStatus = (s: string) =>
    setSelectedStatuses(prev => prev.includes(s) ? prev.filter(x => x !== s) : [...prev, s]);

  const handleExport = async () => {
    const blob = await api.exportAuditLog(filters);
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = 'audit_log.csv'; a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-900">Audit Log</h2>
        <button onClick={handleExport} className="flex items-center gap-1.5 text-sm text-gray-600 border border-gray-300 hover:bg-gray-50 px-3 py-1.5 rounded">
          <Download className="w-4 h-4" /> Export CSV
        </button>
      </div>

      {/* Filters */}
      <div className="bg-white border border-gray-200 rounded-lg p-4 flex flex-wrap gap-3">
        <div className="flex gap-2 items-center">
          <input type="date" value={startDate} onChange={e => { setStartDate(e.target.value); setPage(1); }}
            className="border border-gray-300 rounded text-sm px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-indigo-500" />
          <span className="text-gray-400 text-sm">–</span>
          <input type="date" value={endDate} onChange={e => { setEndDate(e.target.value); setPage(1); }}
            className="border border-gray-300 rounded text-sm px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-indigo-500" />
        </div>
        <input placeholder="Team" value={teamName} onChange={e => { setTeamName(e.target.value); setPage(1); }}
          className="border border-gray-300 rounded text-sm px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-indigo-500 w-36" />
        <div className="flex flex-wrap gap-2 items-center">
          {STATUSES.map(s => (
            <label key={s} className="flex items-center gap-1 text-xs cursor-pointer">
              <input type="checkbox" checked={selectedStatuses.includes(s)} onChange={() => { toggleStatus(s); setPage(1); }} className="accent-indigo-600" />
              <StatusBadge status={s} />
            </label>
          ))}
        </div>
      </div>

      <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b border-gray-200">
            <tr>
              <th className="text-left px-4 py-3 font-medium text-gray-600">Timestamp</th>
              <th className="text-left px-4 py-3 font-medium text-gray-600">Team</th>
              <th className="text-left px-4 py-3 font-medium text-gray-600">Model</th>
              <th className="text-left px-4 py-3 font-medium text-gray-600">Status</th>
              <th className="text-left px-4 py-3 font-medium text-gray-600">Prompt Hash</th>
              <th className="text-left px-4 py-3 font-medium text-gray-600">HTTP</th>
              <th className="text-left px-4 py-3 font-medium text-gray-600">Latency</th>
              <th className="text-left px-4 py-3 font-medium text-gray-600">DLP</th>
              <th className="px-4 py-3 w-8" />
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {isLoading ? (
              <tr><td colSpan={9} className="px-4 py-6"><TableSkeleton cols={8} /></td></tr>
            ) : !data?.items.length ? (
              <tr><td colSpan={9} className="px-4 py-8 text-center text-gray-400">No audit records found</td></tr>
            ) : (
              data.items.flatMap((log: AuditLog) => {
                const expanded = expandedId === log.id;
                return [
                  <tr key={log.id} className="hover:bg-gray-50 cursor-pointer" onClick={() => setExpandedId(expanded ? null : log.id)}>
                    <td className="px-4 py-3 text-gray-600 whitespace-nowrap">{formatDateTime(log.timestamp)}</td>
                    <td className="px-4 py-3 text-gray-700">{log.team_name}</td>
                    <td className="px-4 py-3 text-gray-500 text-xs font-mono truncate max-w-[120px]">{log.model}</td>
                    <td className="px-4 py-3"><StatusBadge status={log.status} /></td>
                    <td className="px-4 py-3"><span className="font-mono text-xs text-gray-400" title={log.prompt_hash}>{log.prompt_hash.slice(0, 12)}…</span></td>
                    <td className="px-4 py-3 text-gray-600">{log.response_status ?? '—'}</td>
                    <td className="px-4 py-3 text-gray-600">{log.latency_ms != null ? `${log.latency_ms}ms` : '—'}</td>
                    <td className="px-4 py-3">
                      {log.dlp_flagged ? <AlertTriangle className="w-4 h-4 text-red-500" /> : <span className="text-gray-300">—</span>}
                    </td>
                    <td className="px-4 py-3">{expanded ? <ChevronUp className="w-4 h-4 text-gray-400" /> : <ChevronDown className="w-4 h-4 text-gray-400" />}</td>
                  </tr>,
                  expanded && (
                    <tr key={`${log.id}-detail`} className="bg-gray-50">
                      <td colSpan={9} className="px-6 py-4">
                        <div className="grid grid-cols-3 gap-x-6 gap-y-2 text-xs">
                          <div className="col-span-3 font-medium text-gray-600 mb-1">Timing Breakdown</div>
                          <div><span className="text-gray-500">Auth:</span> <span className="font-mono">{log.auth_ms ?? '—'}ms</span></div>
                          <div><span className="text-gray-500">DLP scan:</span> <span className="font-mono">{log.dlp_ms ?? '—'}ms</span></div>
                          <div><span className="text-gray-500">Prompt inject:</span> <span className="font-mono">{log.inject_ms ?? '—'}ms</span></div>
                          <div><span className="text-gray-500">vLLM:</span> <span className="font-mono">{log.vllm_ms ?? '—'}ms</span></div>
                          <div><span className="text-gray-500">Total:</span> <span className="font-mono font-medium">{log.latency_ms ?? '—'}ms</span></div>
                          <div><span className="text-gray-500">Tokens:</span> <span className="font-mono">{log.tokens_used ?? '—'}</span></div>
                          {log.dlp_flagged && log.incident_id && (
                            <div className="col-span-3">
                              <span className="text-gray-500">DLP Incident: </span>
                              <button onClick={() => navigate('/dlp-incidents')} className="font-mono text-indigo-600 hover:underline">
                                {log.incident_id}
                              </button>
                            </div>
                          )}
                        </div>
                      </td>
                    </tr>
                  ),
                ].filter(Boolean);
              })
            )}
          </tbody>
        </table>

        {data && data.total_pages > 1 && (
          <div className="px-4 py-3 border-t border-gray-100 flex items-center justify-between text-sm text-gray-600">
            <span>Page {data.page} of {data.total_pages} ({data.total} total)</span>
            <div className="flex gap-2">
              <button disabled={page <= 1} onClick={() => setPage(p => p - 1)} className="px-3 py-1 border rounded disabled:opacity-40 hover:bg-gray-50">Prev</button>
              <button disabled={page >= data.total_pages} onClick={() => setPage(p => p + 1)} className="px-3 py-1 border rounded disabled:opacity-40 hover:bg-gray-50">Next</button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
