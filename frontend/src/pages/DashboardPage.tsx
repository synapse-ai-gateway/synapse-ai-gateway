import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts';
import { api } from '@/lib/api';
import StatCard from '@/components/StatCard';
import SeverityBadge from '@/components/SeverityBadge';
import TableSkeleton from '@/components/TableSkeleton';
import { formatDateTime } from '@/lib/utils';

export default function DashboardPage() {
  const navigate = useNavigate();

  const { data: summary, isLoading: loadingSummary } = useQuery({
    queryKey: ['stats-summary'],
    queryFn: () => api.getStatsSummary(),
    refetchInterval: 30000,
  });

  const { data: perTeam, isLoading: loadingChart } = useQuery({
    queryKey: ['stats-per-team'],
    queryFn: () => api.getStatsPerTeam(),
    refetchInterval: 30000,
  });

  const { data: incidentsPage, isLoading: loadingIncidents } = useQuery({
    queryKey: ['incidents-recent'],
    queryFn: () => api.getIncidents({ page: 1, page_size: 5 }),
    refetchInterval: 30000,
  });

  return (
    <div className="space-y-6">
      <h2 className="text-lg font-semibold text-gray-900">Dashboard</h2>

      {/* Stat cards */}
      <div className="grid grid-cols-4 gap-4">
        <StatCard title="Requests Today" value={summary?.total_requests_today ?? 0} color="blue" loading={loadingSummary} />
        <StatCard title="DLP Blocks Today" value={summary?.dlp_blocks_today ?? 0} color="red" loading={loadingSummary} />
        <StatCard title="Rate Limit Hits" value={summary?.rate_limit_hits_today ?? 0} color="amber" loading={loadingSummary} />
        <StatCard title="Active Teams" value={summary?.active_teams ?? 0} color="green" loading={loadingSummary} />
      </div>

      {/* Chart */}
      <div className="bg-white border border-gray-200 rounded-lg p-5">
        <h3 className="text-sm font-semibold text-gray-900 mb-4">Requests per Team — Last 60 Minutes</h3>
        {loadingChart ? (
          <div className="h-48 bg-gray-100 rounded animate-pulse" />
        ) : (perTeam?.length ?? 0) === 0 ? (
          <div className="h-48 flex items-center justify-center text-sm text-gray-400">No data in the last 60 minutes</div>
        ) : (
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={perTeam} margin={{ top: 4, right: 8, left: -10, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="team_name" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
              <Tooltip />
              <Bar dataKey="count" fill="#4F46E5" radius={[3, 3, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>

      {/* Recent DLP incidents */}
      <div className="bg-white border border-gray-200 rounded-lg">
        <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
          <h3 className="text-sm font-semibold text-gray-900">Recent DLP Incidents</h3>
          <button onClick={() => navigate('/dlp-incidents')} className="text-xs text-indigo-600 hover:underline">
            View all →
          </button>
        </div>
        <div className="divide-y divide-gray-50">
          {loadingIncidents ? (
            <div className="p-5"><TableSkeleton cols={5} rows={3} /></div>
          ) : !incidentsPage?.items.length ? (
            <div className="p-8 text-center text-sm text-gray-400">No DLP incidents yet</div>
          ) : (
            incidentsPage.items.map(inc => (
              <button
                key={inc.id}
                onClick={() => navigate('/dlp-incidents')}
                className="w-full text-left px-5 py-3 hover:bg-gray-50 transition-colors"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <SeverityBadge severity={inc.max_severity} />
                    <span className="text-sm text-gray-700">{inc.team_name}</span>
                    <span className="text-xs text-gray-400 font-mono">{inc.patterns.join(', ')}</span>
                  </div>
                  <span className="text-xs text-gray-400">{formatDateTime(inc.timestamp)}</span>
                </div>
              </button>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
