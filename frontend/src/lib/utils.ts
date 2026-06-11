import { type ClassValue, clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';
import { format, parseISO } from 'date-fns';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function maskApiKey(key: string): string {
  if (!key || key.length <= 8) return key;
  const visible = key.slice(-8);
  const masked = '*'.repeat(Math.min(key.length - 8, 16));
  return `${masked}${visible}`;
}

export function formatDateTime(iso: string): string {
  try {
    return format(parseISO(iso), 'dd MMM yyyy HH:mm:ss');
  } catch {
    return iso;
  }
}

export function formatDate(iso: string): string {
  try {
    return format(parseISO(iso), 'dd MMM yyyy');
  } catch {
    return iso;
  }
}

export function severityColor(severity: string): string {
  switch (severity.toLowerCase()) {
    case 'critical':
      return 'bg-red-100 text-red-800 border-red-200';
    case 'high':
      return 'bg-orange-100 text-orange-800 border-orange-200';
    case 'medium':
      return 'bg-amber-100 text-amber-800 border-amber-200';
    case 'low':
      return 'bg-gray-100 text-gray-700 border-gray-200';
    default:
      return 'bg-gray-100 text-gray-600 border-gray-200';
  }
}

export function statusColor(status: string): string {
  switch (status.toLowerCase()) {
    case 'success':
      return 'bg-green-100 text-green-800 border-green-200';
    case 'blocked_dlp':
      return 'bg-red-100 text-red-800 border-red-200';
    case 'blocked_rate_limit':
      return 'bg-orange-100 text-orange-800 border-orange-200';
    case 'blocked_auth':
      return 'bg-yellow-100 text-yellow-800 border-yellow-200';
    case 'error':
      return 'bg-gray-100 text-gray-700 border-gray-200';
    default:
      return 'bg-gray-100 text-gray-600 border-gray-200';
  }
}

export function roleColor(role: string): string {
  switch (role.toLowerCase()) {
    case 'superadmin':
      return 'bg-purple-100 text-purple-800 border-purple-200';
    case 'admin':
      return 'bg-blue-100 text-blue-800 border-blue-200';
    case 'analyst':
      return 'bg-teal-100 text-teal-800 border-teal-200';
    case 'readonly':
      return 'bg-gray-100 text-gray-700 border-gray-200';
    default:
      return 'bg-gray-100 text-gray-600 border-gray-200';
  }
}

export function truncate(str: string, maxLen: number): string {
  if (!str) return '';
  if (str.length <= maxLen) return str;
  return str.slice(0, maxLen) + '...';
}

export function maskIp(ip: string): string {
  const parts = ip.split('.');
  if (parts.length === 4) {
    return `${parts[0]}.${parts[1]}.${parts[2]}.xxx`;
  }
  return ip;
}

/** Copy text to clipboard with execCommand fallback for non-HTTPS contexts. */
export async function copyToClipboard(text: string): Promise<void> {
  if (navigator.clipboard && window.isSecureContext) {
    await navigator.clipboard.writeText(text);
  } else {
    // Fallback for HTTP (non-secure) contexts
    const el = document.createElement('textarea');
    el.value = text;
    el.style.cssText = 'position:fixed;top:-9999px;left:-9999px;opacity:0';
    document.body.appendChild(el);
    el.focus();
    el.select();
    document.execCommand('copy');
    document.body.removeChild(el);
  }
}

export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
