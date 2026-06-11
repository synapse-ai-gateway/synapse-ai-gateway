import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import type { ActivityLog } from '@/lib/types';
import TableSkeleton from '@/components/TableSkeleton';
import { formatDateTime } from '@/lib/utils';
import { ChevronDown, ChevronUp } from 'lucide-react';

const TARGET_TYPES = ['teams', 'dlp_patterns', 'users', 'settings'];

export default function ActivityLogPage() {
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [username, setUsername] = useState('');
  const [action, setAction] = useState('');
  const [targetType, setTargetType] = useState('');
  const [page, setPage] = useState(1);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const filters = {
    start_date: startDate || undefined,
    end_date: endDate || undefined,
    username: username || undefined,
    action: action || undefined,
    target_type: targetType || undefined,
    page,
    page_size: 20,
  };

  const { data, isLoading } = useQuery({
    queryKey: ['activity-log', filters],
    queryFn: () => api.getActivityLog(filters),
  });

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-semibold text-gray-900">Activity Log</h2>

      {/* Filters */}
      <div className="bg-white border border-gray-200 rounded-lg p-4 flex flex-wrap gap-3">
        <div className="flex gap-2 items-center">
          <input type="date" value={startDate} onChange={e => { setStartDate(e.target.value); setPage(1); }}
            className="border border-gray-300 rounded text-sm px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-indigo-500" />
          <span className="text-gray-400 text-sm">–</span>
          <input type="date" value={endDate} onChange={e => { setEndDate(e.target.value); setPage(1); }}
            className="border border-gray-300 rounded text-sm px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-indigo-500" />
        </div>
        <input placeholder="Username" value={username} onChange={e => { setUsername(e.target.value); setPage(1); }}
          className="border border-gray-300 rounded text-sm px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-indigo-500 w-32" />
        <input placeholder="Action" value={action} onChange={e => { setAction(e.target.value); setPage(1); }}
          className="border border-gray-300 rounded text-sm px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-indigo-500 w-36" />
        <select value={targetType} onChange={e => { setTargetType(e.target.value); setPage(1); }}
          className="border border-gray-300 rounded text-sm px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-indigo-500">
          <option value="">All types</option>
          {TARGET_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
        </select>
      </div>

      <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b border-gray-200">
            <tr>
              <th className="text-left px-4 py-3 font-medium text-gray-600">Timestamp</th>
              <th className="text-left px-4 py-3 font-medium text-gray-600">User</th>
              <th className="text-left px-4 py-3 font-medium text-gray-600">Action</th>
              <th className="text-left px-4 py-3 font-medium text-gray-600">Target Type</th>
              <th className="text-left px-4 py-3 font-medium text-gray-600">Target ID</th>
              <th className="text-left px-4 py-3 font-medium text-gray-600">IP</th>
              <th className="px-4 py-3 w-8" />
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {isLoading ? (
              <tr><td colSpan={7} className="px-4 py-6"><TableSkeleton cols={6} /></td></tr>
            ) : !data?.items.length ? (
              <tr><td colSpan={7} className="px-4 py-8 text-center text-gray-400">No activity records found</td></tr>
            ) : (
              data.items.flatMap((log: ActivityLog) => {
                const expanded = expandedId === log.id;
                return [
                  <tr key={log.id} className="hover:bg-gray-50 cursor-pointer" onClick={() => setExpandedId(expanded ? null : log.id)}>
                    <td className="px-4 py-3 text-gray-600 whitespace-nowrap">{formatDateTime(log.timestamp)}</td>
                    <td className="px-4 py-3 font-medium text-gray-900">{log.username}</td>
                    <td className="px-4 py-3">
                      <span className="font-mono text-xs bg-gray-100 text-gray-700 px-1.5 py-0.5 rounded">{log.action}</span>
                    </td>
                    <td className="px-4 py-3 text-gray-500 text-xs">{log.target_type}</td>
                    <td className="px-4 py-3 text-gray-600 text-xs font-mono">{log.target_id}</td>
                    <td className="px-4 py-3 text-gray-400 text-xs font-mono">{log.ip_address ?? '—'}</td>
                    <td className="px-4 py-3">{expanded ? <ChevronUp className="w-4 h-4 text-gray-400" /> : <ChevronDown className="w-4 h-4 text-gray-400" />}</td>
                  </tr>,
                  expanded && log.changes && (
                    <tr key={`${log.id}-detail`} className="bg-gray-50">
                      <td colSpan={7} className="px-6 py-4">
                        <p className="text-xs font-medium text-gray-600 mb-2">Changes</p>
                        <div className="space-y-2">
                          {Object.entries(log.changes).map(([field, change]) => {
                            if (!change || typeof change !== 'object') return null;
                            const c = change as { old?: unknown; new?: unknown };
                            return (
                              <div key={field} className="flex items-start gap-4 text-xs">
                                <span className="font-medium text-gray-600 w-24 shrink-0">{field}</span>
                                <span className="text-red-600 line-through">{String(c.old ?? '')}</span>
                                <span className="text-gray-400">→</span>
                                <span className="text-green-700">{String(c.new ?? '')}</span>
                              </div>
                            );
                          })}
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
