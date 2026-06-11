import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import type { DlpIncident } from '@/lib/types';
import SeverityBadge from '@/components/SeverityBadge';
import TableSkeleton from '@/components/TableSkeleton';
import { formatDateTime } from '@/lib/utils';
import { Download, ChevronDown, ChevronUp } from 'lucide-react';

const SEVERITIES = ['critical', 'high', 'medium', 'low'];

function maskIp(ip: string) {
  const parts = ip.split('.');
  if (parts.length === 4) { parts[3] = 'xxx'; return parts.join('.'); }
  return ip;
}

export default function DlpIncidentsPage() {
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [selectedSeverities, setSelectedSeverities] = useState<string[]>([]);
  const [teamName, setTeamName] = useState('');
  const [incidentId, setIncidentId] = useState('');
  const [page, setPage] = useState(1);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const filters = {
    start_date: startDate || undefined,
    end_date: endDate || undefined,
    severities: selectedSeverities.length ? selectedSeverities : undefined,
    team_name: teamName || undefined,
    incident_id: incidentId || undefined,
    page,
    page_size: 20,
  };

  const { data, isLoading } = useQuery({
    queryKey: ['incidents', filters],
    queryFn: () => api.getIncidents(filters),
  });

  const toggleSeverity = (s: string) =>
    setSelectedSeverities(prev => prev.includes(s) ? prev.filter(x => x !== s) : [...prev, s]);

  const handleExport = async () => {
    const blob = await api.exportIncidents(filters);
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = 'dlp_incidents.csv'; a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-900">DLP Incidents</h2>
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
        <div className="flex gap-2 items-center">
          {SEVERITIES.map(s => (
            <label key={s} className="flex items-center gap-1 text-sm cursor-pointer">
              <input type="checkbox" checked={selectedSeverities.includes(s)} onChange={() => { toggleSeverity(s); setPage(1); }} className="accent-indigo-600" />
              <SeverityBadge severity={s} />
            </label>
          ))}
        </div>
        <input placeholder="Team" value={teamName} onChange={e => { setTeamName(e.target.value); setPage(1); }}
          className="border border-gray-300 rounded text-sm px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-indigo-500 w-32" />
        <input placeholder="Incident ID" value={incidentId} onChange={e => { setIncidentId(e.target.value); setPage(1); }}
          className="border border-gray-300 rounded text-sm px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-indigo-500 w-52 font-mono" />
      </div>

      <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b border-gray-200">
            <tr>
              <th className="text-left px-4 py-3 font-medium text-gray-600">Timestamp</th>
              <th className="text-left px-4 py-3 font-medium text-gray-600">Incident ID</th>
              <th className="text-left px-4 py-3 font-medium text-gray-600">Team</th>
              <th className="text-left px-4 py-3 font-medium text-gray-600">Patterns</th>
              <th className="text-left px-4 py-3 font-medium text-gray-600">Severity</th>
              <th className="text-left px-4 py-3 font-medium text-gray-600">Len</th>
              <th className="text-left px-4 py-3 font-medium text-gray-600">Source</th>
              <th className="px-4 py-3 w-8" />
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {isLoading ? (
              <tr><td colSpan={8} className="px-4 py-6"><TableSkeleton cols={7} /></td></tr>
            ) : !data?.items.length ? (
              <tr><td colSpan={8} className="px-4 py-8 text-center text-gray-400">No incidents found</td></tr>
            ) : (
              data.items.flatMap((inc: DlpIncident) => {
                const expanded = expandedId === inc.incident_id;
                return [
                  <tr key={inc.incident_id} className="hover:bg-gray-50 cursor-pointer" onClick={() => setExpandedId(expanded ? null : inc.incident_id)}>
                    <td className="px-4 py-3 text-gray-600 whitespace-nowrap">{formatDateTime(inc.timestamp)}</td>
                    <td className="px-4 py-3">
                      <span className="font-mono text-xs text-gray-500" title={inc.incident_id}>{inc.incident_id.slice(0, 8)}…</span>
                    </td>
                    <td className="px-4 py-3 text-gray-700">{inc.team_name}</td>
                    <td className="px-4 py-3">
                      <div className="flex flex-wrap gap-1">
                        {inc.patterns.map(p => (
                          <span key={p} className="text-xs bg-gray-100 text-gray-700 px-1.5 py-0.5 rounded">{p}</span>
                        ))}
                      </div>
                    </td>
                    <td className="px-4 py-3"><SeverityBadge severity={inc.max_severity} /></td>
                    <td className="px-4 py-3 text-gray-600">{inc.message_len}</td>
                    <td className="px-4 py-3 text-gray-600 text-xs">{inc.source}</td>
                    <td className="px-4 py-3">{expanded ? <ChevronUp className="w-4 h-4 text-gray-400" /> : <ChevronDown className="w-4 h-4 text-gray-400" />}</td>
                  </tr>,
                  expanded && (
                    <tr key={`${inc.incident_id}-detail`} className="bg-gray-50">
                      <td colSpan={8} className="px-6 py-4">
                        <div className="grid grid-cols-2 gap-x-8 gap-y-2 text-xs">
                          <div><span className="font-medium text-gray-600">Incident ID:</span> <span className="font-mono text-gray-800">{inc.incident_id}</span></div>
                          <div><span className="font-medium text-gray-600">API Key:</span> <span className="font-mono text-gray-800">…{(inc.api_key ?? '').slice(-8)}</span></div>
                          <div><span className="font-medium text-gray-600">Client IP:</span> <span className="font-mono text-gray-800">{maskIp(inc.client_ip)}</span></div>
                          <div><span className="font-medium text-gray-600">Source:</span> <span className="text-gray-800">{inc.source}</span></div>
                          <div className="col-span-2">
                            <span className="font-medium text-gray-600">Matched Patterns: </span>
                            {inc.patterns.map((p, i) => (
                              <span key={p}>{p} ({inc.severities[i]}){Object.entries(inc.match_counts).find(([k]) => k === p) ? ` ×${inc.match_counts[p]}` : ''}{i < inc.patterns.length - 1 ? ', ' : ''}</span>
                            ))}
                          </div>
                        </div>
                      </td>
                    </tr>
                  ),
                ].filter(Boolean);
              })
            )}
          </tbody>
        </table>

        {/* Pagination */}
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
