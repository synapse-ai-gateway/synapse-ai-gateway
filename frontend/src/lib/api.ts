import { mockApi } from './mockApi';
import type {
  LoginResponse,
  Team,
  DlpIncident,
  AuditLog,
  DlpPattern,
  GatewaySettings,
  ActivityLog,
  StatsSummary,
  PerTeamStat,
  PaginatedResponse,
  User,
  CreateTeamRequest,
  UpdateTeamRequest,
  CreateUserRequest,
  UpdateUserRequest,
  CreateDlpPatternRequest,
  UpdateDlpPatternRequest,
  IncidentFilters,
  AuditFilters,
  ActivityFilters,
} from './types';

const ENV_MOCK = import.meta.env.VITE_USE_MOCK === 'true';
const BASE_URL = import.meta.env.VITE_GATEWAY_URL || 'http://localhost:8080';

const MOCK_KEY = 'sg_use_mock';

export function isMockEnabled(): boolean {
  const stored = localStorage.getItem(MOCK_KEY);
  if (stored !== null) return stored === 'true';
  return ENV_MOCK;
}

export function setMockEnabled(value: boolean): void {
  localStorage.setItem(MOCK_KEY, String(value));
}

let _token: string | null = null;
let _onUnauthorized: (() => void) | null = null;

export function setToken(token: string | null) {
  _token = token;
}

export function setOnUnauthorized(cb: () => void) {
  _onUnauthorized = cb;
}

async function request<T>(
  method: string,
  path: string,
  body?: unknown,
  options?: { responseType?: 'blob' }
): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  if (_token) {
    headers['Authorization'] = `Bearer ${_token}`;
  }

  const res = await fetch(`${BASE_URL}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });

  if (res.status === 401) {
    _onUnauthorized?.();
    throw { status: 401, message: 'Unauthorized' };
  }

  if (!res.ok) {
    let message = res.statusText;
    try {
      const json = await res.json();
      message = json.detail || json.message || message;
    } catch {
      // ignore
    }
    throw { status: res.status, message };
  }

  if (options?.responseType === 'blob') {
    return res.blob() as unknown as T;
  }

  if (res.status === 204) {
    return undefined as unknown as T;
  }

  return res.json();
}

export const api = {
  // ── Auth ────────────────────────────────────────────────────────────────────
  login: async (username: string, password: string): Promise<LoginResponse> => {
    if (isMockEnabled()) return mockApi.login(username, password);
    // Use raw fetch — must NOT go through request() because request() calls
    // _onUnauthorized on 401, which would navigate away before the error shows.
    const res = await fetch(`${BASE_URL}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    });
    if (!res.ok) {
      let detail: unknown;
      try { detail = (await res.json()).detail; } catch { detail = null; }
      throw { status: res.status, message: detail ?? res.statusText, detail };
    }
    return res.json();
  },

  changePassword: async (current_password: string, new_password: string): Promise<void> => {
    if (isMockEnabled()) return mockApi.changePassword(current_password, new_password);
    return request<void>('POST', '/auth/change-password', { current_password, new_password });
  },

  refreshToken: async (): Promise<LoginResponse> => {
    if (isMockEnabled()) return {} as LoginResponse;
    return request<LoginResponse>('POST', '/auth/refresh');
  },

  logout: async (): Promise<void> => {
    if (isMockEnabled()) return mockApi.logout();
    return request<void>('POST', '/auth/logout');
  },

  // ── Teams ───────────────────────────────────────────────────────────────────
  getTeams: async (): Promise<Team[]> => {
    if (isMockEnabled()) return mockApi.getTeams();
    return request<Team[]>('GET', '/admin/teams');
  },

  createTeam: async (data: CreateTeamRequest): Promise<Team> => {
    if (isMockEnabled()) return mockApi.createTeam(data);
    return request<Team>('POST', '/admin/teams', data);
  },

  getTeamApiKey: async (id: number): Promise<string> => {
    const res = await request<{ api_key: string }>('GET', `/admin/teams/${id}/api-key`);
    return res.api_key;
  },

  updateTeam: async (id: number, data: UpdateTeamRequest): Promise<Team> => {
    if (isMockEnabled()) return mockApi.updateTeam(String(id), data);
    return request<Team>('PATCH', `/admin/teams/${id}`, data);
  },

  deleteTeam: async (id: number): Promise<void> => {
    if (isMockEnabled()) return mockApi.deleteTeam(String(id));
    return request<void>('DELETE', `/admin/teams/${id}`);
  },

  // ── DLP Incidents ───────────────────────────────────────────────────────────
  getIncidents: async (filters: IncidentFilters = {}): Promise<PaginatedResponse<DlpIncident>> => {
    if (isMockEnabled()) return mockApi.getIncidents(filters);
    const params = new URLSearchParams();
    Object.entries(filters).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== '') {
        if (Array.isArray(v)) v.forEach(item => params.append(k, item));
        else params.set(k, String(v));
      }
    });
    return request<PaginatedResponse<DlpIncident>>('GET', `/admin/incidents?${params}`);
  },

  exportIncidents: async (filters: IncidentFilters = {}): Promise<Blob> => {
    if (isMockEnabled()) return mockApi.exportIncidents(filters);
    const params = new URLSearchParams();
    Object.entries(filters).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== '') {
        if (Array.isArray(v)) v.forEach(item => params.append(k, item));
        else params.set(k, String(v));
      }
    });
    return request<Blob>('GET', `/admin/incidents/export?${params}`, undefined, { responseType: 'blob' });
  },

  // ── Audit Log ───────────────────────────────────────────────────────────────
  getAuditLog: async (filters: AuditFilters = {}): Promise<PaginatedResponse<AuditLog>> => {
    if (isMockEnabled()) return mockApi.getAuditLog(filters);
    const params = new URLSearchParams();
    Object.entries(filters).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== '') {
        if (Array.isArray(v)) v.forEach(item => params.append(k, item));
        else params.set(k, String(v));
      }
    });
    return request<PaginatedResponse<AuditLog>>('GET', `/admin/audit?${params}`);
  },

  exportAuditLog: async (filters: AuditFilters = {}): Promise<Blob> => {
    if (isMockEnabled()) return mockApi.exportAuditLog(filters);
    const params = new URLSearchParams();
    Object.entries(filters).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== '') {
        if (Array.isArray(v)) v.forEach(item => params.append(k, item));
        else params.set(k, String(v));
      }
    });
    return request<Blob>('GET', `/admin/audit/export?${params}`, undefined, { responseType: 'blob' });
  },

  // ── Stats ───────────────────────────────────────────────────────────────────
  getStatsSummary: async (): Promise<StatsSummary> => {
    if (isMockEnabled()) return mockApi.getStatsSummary();
    return request<StatsSummary>('GET', '/admin/stats/summary');
  },

  getStatsPerTeam: async (): Promise<PerTeamStat[]> => {
    if (isMockEnabled()) return mockApi.getStatsPerTeam();
    return request<PerTeamStat[]>('GET', '/admin/stats/per-team');
  },

  // ── DLP Patterns ────────────────────────────────────────────────────────────
  getDlpPatterns: async (): Promise<DlpPattern[]> => {
    if (isMockEnabled()) return mockApi.getDlpPatterns();
    return request<DlpPattern[]>('GET', '/admin/dlp-patterns');
  },

  createDlpPattern: async (data: CreateDlpPatternRequest): Promise<DlpPattern> => {
    if (isMockEnabled()) return mockApi.createDlpPattern(data);
    return request<DlpPattern>('POST', '/admin/dlp-patterns', data);
  },

  updateDlpPattern: async (name: string, data: UpdateDlpPatternRequest): Promise<DlpPattern> => {
    if (isMockEnabled()) return mockApi.updateDlpPattern(name, data);
    return request<DlpPattern>('PATCH', `/admin/dlp-patterns/${encodeURIComponent(name)}`, data);
  },

  deleteDlpPattern: async (name: string): Promise<void> => {
    if (isMockEnabled()) return mockApi.deleteDlpPattern(name);
    return request<void>('DELETE', `/admin/dlp-patterns/${encodeURIComponent(name)}`);
  },

  // ── Gateway Settings ────────────────────────────────────────────────────────
  getSettings: async (): Promise<GatewaySettings> => {
    if (isMockEnabled()) return mockApi.getSettings();
    return request<GatewaySettings>('GET', '/admin/settings');
  },

  updateSettings: async (data: Partial<GatewaySettings>): Promise<GatewaySettings> => {
    if (isMockEnabled()) return mockApi.updateSettings(data as GatewaySettings);
    return request<GatewaySettings>('PATCH', '/admin/settings', data);
  },

  // ── Users ───────────────────────────────────────────────────────────────────
  getUsers: async (): Promise<User[]> => {
    if (isMockEnabled()) return mockApi.getUsers();
    return request<User[]>('GET', '/admin/users');
  },

  createUser: async (data: CreateUserRequest): Promise<User> => {
    if (isMockEnabled()) return mockApi.createUser(data);
    return request<User>('POST', '/admin/users', data);
  },

  updateUser: async (id: string, data: UpdateUserRequest): Promise<User> => {
    if (isMockEnabled()) return mockApi.updateUser(id, data);
    return request<User>('PATCH', `/admin/users/${id}`, data);
  },

  resetPassword: async (id: string): Promise<{ temp_password: string }> => {
    if (isMockEnabled()) return mockApi.resetPassword(id);
    return request<{ temp_password: string }>('POST', `/admin/users/${id}/reset-password`);
  },

  // ── Activity Log ────────────────────────────────────────────────────────────
  getActivityLog: async (filters: ActivityFilters = {}): Promise<PaginatedResponse<ActivityLog>> => {
    if (isMockEnabled()) return mockApi.getActivityLog(filters);
    const params = new URLSearchParams();
    Object.entries(filters).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== '') params.set(k, String(v));
    });
    return request<PaginatedResponse<ActivityLog>>('GET', `/admin/activity-log?${params}`);
  },

  exportActivityLog: async (): Promise<Blob> => {
    if (isMockEnabled()) return mockApi.exportActivityLog();
    // Export activity log by fetching a large page and converting client-side
    const data = await request<PaginatedResponse<ActivityLog>>('GET', '/admin/activity-log?page_size=1000');
    const header = 'timestamp,username,action,target_type,target_id,ip_address\n';
    const rows = data.items.map((l: ActivityLog) =>
      `${l.timestamp},${l.username},${l.action},${l.target_type},${l.target_id},${l.ip_address ?? ''}`
    ).join('\n');
    return new Blob([header + rows], { type: 'text/csv' });
  },

  // ── Models ──────────────────────────────────────────────────────────────────
  getAvailableModels: async (): Promise<string[]> => {
    if (isMockEnabled()) return mockApi.getAvailableModels();
    const res = await request<{ models: string[] }>('GET', '/admin/models');
    return res.models;
  },
};
