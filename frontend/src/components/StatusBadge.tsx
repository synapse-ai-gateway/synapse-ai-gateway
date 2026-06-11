const classes: Record<string, string> = {
  success:              'bg-green-100 text-green-800 border-green-200',
  blocked_dlp:          'bg-red-100 text-red-800 border-red-200',
  blocked_rate_limit:   'bg-orange-100 text-orange-800 border-orange-200',
  blocked_auth:         'bg-yellow-100 text-yellow-800 border-yellow-200',
  error:                'bg-gray-100 text-gray-700 border-gray-200',
};

const labels: Record<string, string> = {
  success:            'Success',
  blocked_dlp:        'DLP Block',
  blocked_rate_limit: 'Rate Limited',
  blocked_auth:       'Auth Blocked',
  error:              'Error',
};

export default function StatusBadge({ status }: { status: string }) {
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium border ${classes[status] ?? 'bg-gray-100 text-gray-700 border-gray-200'}`}>
      {labels[status] ?? status}
    </span>
  );
}
