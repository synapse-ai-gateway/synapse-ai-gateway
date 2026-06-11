import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { RefreshCw, AlertTriangle } from 'lucide-react';

interface ModelSelectProps {
  value: string;
  onChange: (value: string) => void;
  className?: string;
}

export default function ModelSelect({ value, onChange, className = '' }: ModelSelectProps) {
  const { data: models = [], isLoading, isError, error, refetch } = useQuery({
    queryKey: ['available-models'],
    queryFn: api.getAvailableModels,
    staleTime: 60000,
    retry: 1,
  });

  // Extract the error message returned by the backend
  const errorMsg: string = isError
    ? ((error as { message?: string })?.message ?? 'Could not reach LLM backend')
    : '';

  const allOptions = models.includes(value) || !value
    ? models
    : [value, ...models]; // keep current value even if not in list

  return (
    <div className="flex flex-col gap-1">
      <div className="flex gap-2">
        <div className="flex-1 relative">
          <select
            value={value}
            onChange={e => onChange(e.target.value)}
            className={`w-full px-3 py-2 border rounded text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 bg-white ${
              isError ? 'border-red-400' : 'border-gray-300'
            } ${className}`}
          >
            {isLoading && <option value="">Loading models…</option>}
            {isError && <option value="">— LLM backend unreachable —</option>}
            {!isLoading && !isError && models.length === 0 && (
              <option value="">No models found — is Ollama running?</option>
            )}
            {allOptions.map(m => (
              <option key={m} value={m}>{m}</option>
            ))}
          </select>
        </div>

        {/* Manual override input — user can type a custom model name */}
        <input
          type="text"
          value={value}
          onChange={e => onChange(e.target.value)}
          placeholder="or type model name"
          className="w-44 px-3 py-2 border border-gray-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 font-mono"
        />

        <button
          type="button"
          onClick={() => refetch()}
          title="Refresh model list"
          className="p-2 border border-gray-300 rounded hover:bg-gray-50 text-gray-500 hover:text-gray-700"
        >
          <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {/* Show backend error detail below the control */}
      {isError && (
        <div className="flex items-start gap-1.5 text-xs text-red-600 bg-red-50 border border-red-200 rounded px-2 py-1.5">
          <AlertTriangle className="w-3.5 h-3.5 mt-0.5 shrink-0" />
          <span>{errorMsg}</span>
        </div>
      )}
    </div>
  );
}
