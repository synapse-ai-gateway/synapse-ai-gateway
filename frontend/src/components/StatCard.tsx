interface StatCardProps {
  title: string;
  value: string | number;
  color?: 'blue' | 'amber' | 'red' | 'green';
  loading?: boolean;
}

const borderColors = {
  blue: 'border-indigo-500',
  amber: 'border-amber-500',
  red: 'border-rose-500',
  green: 'border-emerald-500',
};

export default function StatCard({ title, value, color = 'blue', loading }: StatCardProps) {
  return (
    <div className={`bg-white rounded-xl border border-gray-200 border-l-4 ${borderColors[color]} p-5 shadow-sm`}>
      <p className="text-sm text-gray-500 mb-1">{title}</p>
      {loading ? (
        <div className="h-8 w-20 bg-gray-200 rounded animate-pulse" />
      ) : (
        <p className="text-3xl font-bold text-gray-900">{value}</p>
      )}
    </div>
  );
}
