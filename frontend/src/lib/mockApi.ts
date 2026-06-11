import { subDays, subHours, subMinutes, formatISO } from 'date-fns';
import type {
  User,
  Team,
  DlpIncident,
  AuditLog,
  DlpPattern,
  GatewaySettings,
  ActivityLog,
  StatsSummary,
  PerTeamStat,
  PaginatedResponse,
  LoginResponse,
  IncidentFilters,
  AuditFilters,
  ActivityFilters,
  CreateTeamRequest,
  UpdateTeamRequest,
  CreateUserRequest,
  UpdateUserRequest,
  CreateDlpPatternRequest,
  UpdateDlpPatternRequest,
} from './types';

const delay = (ms = 300) => new Promise((resolve) => setTimeout(resolve, ms));

const now = new Date();

// ─── Mock Users ────────────────────────────────────────────────────────────────
const mockUsers: User[] = [
  {
    id: 'usr-001',
    username: 'admin',
    email: 'admin@yourorg.com',
    full_name: 'System Administrator',
    role: 'superadmin',
    enabled: true,
    force_password_change: false,
    last_login: formatISO(subMinutes(now, 15)),
    created_by: 'system',
    created_at: formatISO(subDays(now, 90)),
    updated_at: formatISO(subDays(now, 2)),
  },
  {
    id: 'usr-002',
    username: 'ops_manager',
    email: 'ops.manager@yourorg.com',
    full_name: 'Operations Manager',
    role: 'admin',
    enabled: true,
    force_password_change: false,
    last_login: formatISO(subHours(now, 2)),
    created_by: 'admin',
    created_at: formatISO(subDays(now, 60)),
    updated_at: formatISO(subDays(now, 5)),
  },
  {
    id: 'usr-003',
    username: 'data_analyst',
    email: 'data.analyst@yourorg.com',
    full_name: 'Data Analyst',
    role: 'analyst',
    enabled: true,
    force_password_change: false,
    last_login: formatISO(subHours(now, 8)),
    created_by: 'admin',
    created_at: formatISO(subDays(now, 30)),
    updated_at: formatISO(subDays(now, 10)),
  },
];

// ─── Mock Teams ─────────────────────────────────────────────────────────────────
const mockTeams: Team[] = [
  {
    id: 1,
    api_key: 'sg-gw-a1b2c3d4e5f6g7h8',
    team_name: 'Retail Banking',
    model: 'llama-3.1-8b-instruct',
    requests: 100,
    window_sec: 60,
    enabled: true,
    system_prompt: 'You are a helpful banking assistant for retail customers. Always respond professionally and never disclose internal systems.',
    created_by: 'admin',
    created_at: formatISO(subDays(now, 45)),
    updated_at: formatISO(subDays(now, 3)),
  },
  {
    id: 2,
    api_key: 'sg-gw-b2c3d4e5f6g7h8i9',
    team_name: 'Corporate Treasury',
    model: 'llama-3.1-70b-instruct',
    requests: 200,
    window_sec: 60,
    enabled: true,
    system_prompt: 'You are a financial analysis assistant for the corporate treasury team. Provide detailed financial insights based on the data provided.',
    created_by: 'admin',
    created_at: formatISO(subDays(now, 40)),
    updated_at: formatISO(subDays(now, 1)),
  },
  {
    id: 3,
    api_key: 'sg-gw-c3d4e5f6g7h8i9j0',
    team_name: 'Risk & Compliance',
    model: 'llama-3.1-8b-instruct',
    requests: 50,
    window_sec: 60,
    enabled: true,
    system_prompt: 'You are a compliance assistant. Help identify regulatory requirements and assess risk factors based on provided documentation.',
    created_by: 'ops_manager',
    created_at: formatISO(subDays(now, 30)),
    updated_at: formatISO(subDays(now, 7)),
  },
  {
    id: 4,
    api_key: 'sg-gw-d4e5f6g7h8i9j0k1',
    team_name: 'IT Operations',
    model: 'llama-3.1-8b-instruct',
    requests: 300,
    window_sec: 300,
    enabled: true,
    system_prompt: 'You are an IT support assistant. Help with technical issues, infrastructure queries, and operational procedures.',
    created_by: 'admin',
    created_at: formatISO(subDays(now, 20)),
    updated_at: formatISO(subDays(now, 4)),
  },
  {
    id: 5,
    api_key: 'sg-gw-e5f6g7h8i9j0k1l2',
    team_name: 'HR & Talent',
    model: 'llama-3.1-8b-instruct',
    requests: 30,
    window_sec: 60,
    enabled: false,
    system_prompt: 'You are an HR assistant. Assist with HR queries, policy information, and talent management processes.',
    created_by: 'ops_manager',
    created_at: formatISO(subDays(now, 10)),
    updated_at: formatISO(subDays(now, 2)),
  },
];

// ─── Mock DLP Patterns ──────────────────────────────────────────────────────────
// The default pack ships a jurisdiction-diverse sample (US SSN, UK NINO, generic
// IBAN, E.164 phone) plus universal patterns (credit card, email, AWS key).
// Production deployments should customise these via DLP_PATTERNS_FILE for their
// own regulatory context — see docs/dlp-configuration.md.
const mockDlpPatterns: DlpPattern[] = [
  {
    id: 'pat-001',
    name: 'Credit Card Number',
    pattern: '\\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13})\\b',
    severity: 'critical',
    enabled: true,
    created_by: 'admin',
    created_at: formatISO(subDays(now, 80)),
  },
  {
    id: 'pat-002',
    name: 'US Social Security Number',
    pattern: '\\b(?!000|666|9\\d{2})\\d{3}-(?!00)\\d{2}-(?!0000)\\d{4}\\b',
    severity: 'critical',
    enabled: true,
    created_by: 'admin',
    created_at: formatISO(subDays(now, 80)),
  },
  {
    id: 'pat-003',
    name: 'UK National Insurance Number',
    pattern: '\\b[A-CEGHJ-PR-TW-Z]{2}\\d{6}[A-D]\\b',
    severity: 'critical',
    enabled: true,
    created_by: 'admin',
    created_at: formatISO(subDays(now, 78)),
  },
  {
    id: 'pat-004',
    name: 'IBAN',
    pattern: '\\b[A-Z]{2}\\d{2}[A-Z0-9]{11,30}\\b',
    severity: 'high',
    enabled: true,
    created_by: 'admin',
    created_at: formatISO(subDays(now, 75)),
  },
  {
    id: 'pat-005',
    name: 'AWS Access Key',
    pattern: '\\bAKIA[0-9A-Z]{16}\\b',
    severity: 'high',
    enabled: true,
    created_by: 'admin',
    created_at: formatISO(subDays(now, 70)),
  },
  {
    id: 'pat-006',
    name: 'Email Address',
    pattern: '\\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}\\b',
    severity: 'medium',
    enabled: true,
    created_by: 'ops_manager',
    created_at: formatISO(subDays(now, 60)),
  },
  {
    id: 'pat-007',
    name: 'Phone Number (E.164)',
    pattern: '\\b\\+[1-9]\\d{6,14}\\b',
    severity: 'medium',
    enabled: true,
    created_by: 'ops_manager',
    created_at: formatISO(subDays(now, 55)),
  },
  {
    id: 'pat-008',
    name: 'Internal IP Range',
    pattern: '\\b10\\.(?:[0-9]{1,3}\\.){2}[0-9]{1,3}\\b',
    severity: 'low',
    enabled: false,
    created_by: 'data_analyst',
    created_at: formatISO(subDays(now, 20)),
  },
];

// ─── Mock DLP Incidents ─────────────────────────────────────────────────────────
const severityList = ['critical', 'high', 'medium', 'low'];
const patternNames = [
  'Credit Card Number',
  'US Social Security Number',
  'UK National Insurance Number',
  'IBAN',
  'AWS Access Key',
  'Email Address',
  'Phone Number (E.164)',
];
const sourceList = ['request', 'response'];
const teamNames = mockTeams.map((t) => t.team_name);
const teamApiKeys = mockTeams.map((t) => t.api_key);

function randomFrom<T>(arr: T[]): T {
  return arr[Math.floor(Math.random() * arr.length)];
}

function makeIncidents(): DlpIncident[] {
  const incidents: DlpIncident[] = [];
  for (let i = 0; i < 20; i++) {
    const teamIdx = Math.floor(Math.random() * (mockTeams.length - 1)); // exclude disabled team mostly
    const numPatterns = Math.floor(Math.random() * 3) + 1;
    const patterns = Array.from(new Set(Array.from({ length: numPatterns }, () => randomFrom(patternNames))));
    const sev: string[] = patterns.map(() => randomFrom(severityList));
    const maxSev = sev.reduce((a, b) => {
      const order = ['low', 'medium', 'high', 'critical'];
      return order.indexOf(a) > order.indexOf(b) ? a : b;
    }, 'low');
    const matchCounts: Record<string, number> = {};
    patterns.forEach((p) => { matchCounts[p] = Math.floor(Math.random() * 5) + 1; });
    incidents.push({
      id: `inc-${String(i + 1).padStart(3, '0')}`,
      incident_id: `INC-${Date.now()}-${Math.random().toString(36).slice(2, 8).toUpperCase()}`,
      api_key: teamApiKeys[teamIdx],
      team_name: teamNames[teamIdx],
      client_ip: `10.0.${Math.floor(Math.random() * 10)}.${Math.floor(Math.random() * 254) + 1}`,
      patterns,
      severities: sev,
      max_severity: maxSev,
      match_counts: matchCounts,
      message_len: Math.floor(Math.random() * 2000) + 100,
      source: randomFrom(sourceList),
      timestamp: formatISO(subMinutes(now, Math.floor(Math.random() * 10080))),
    });
  }
  return incidents.sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime());
}

const mockIncidents = makeIncidents();

// ─── Mock Audit Logs ────────────────────────────────────────────────────────────
const auditStatuses = ['success', 'blocked_dlp', 'blocked_rate_limit', 'blocked_auth', 'error'];
const auditModels = ['llama-3.1-8b-instruct', 'llama-3.1-70b-instruct'];

function makeAuditLogs(): AuditLog[] {
  const logs: AuditLog[] = [];
  for (let i = 0; i < 50; i++) {
    const teamIdx = Math.floor(Math.random() * mockTeams.length);
    const status = randomFrom(auditStatuses);
    const dlpFlagged = status === 'blocked_dlp';
    const latency = Math.floor(Math.random() * 3000) + 50;
    const authMs = Math.floor(Math.random() * 20) + 2;
    const dlpMs = Math.floor(Math.random() * 50) + 5;
    const injectMs = Math.floor(Math.random() * 10) + 1;
    const vllmMs = latency - authMs - dlpMs - injectMs;
    const incidentId = dlpFlagged ? mockIncidents[Math.floor(Math.random() * mockIncidents.length)].incident_id : null;
    logs.push({
      id: `log-${String(i + 1).padStart(3, '0')}`,
      api_key: teamApiKeys[teamIdx],
      team_name: teamNames[teamIdx],
      model: randomFrom(auditModels),
      status,
      prompt_hash: Math.random().toString(36).slice(2, 18),
      response_status: status === 'success' ? 200 : status === 'error' ? 500 : 403,
      latency_ms: latency,
      auth_ms: authMs,
      dlp_ms: dlpMs,
      inject_ms: injectMs,
      vllm_ms: Math.max(vllmMs, 10),
      dlp_flagged: dlpFlagged,
      incident_id: incidentId,
      tokens_used: Math.floor(Math.random() * 1500) + 50,
      client_ip: `10.0.${Math.floor(Math.random() * 10)}.${Math.floor(Math.random() * 254) + 1}`,
      timestamp: formatISO(subMinutes(now, Math.floor(Math.random() * 10080))),
    });
  }
  return logs.sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime());
}

const mockAuditLogs = makeAuditLogs();

// ─── Mock Gateway Settings ───────────────────────────────────────────────────────
const mockSettings: GatewaySettings = {
  vllm_endpoint: 'http://localhost:11434/v1',
  default_model: 'llama-3.1-8b-instruct',
  request_timeout_sec: '30',
  default_rate_limit_requests: '100',
  default_rate_limit_window_sec: '60',
  max_tokens: '4096',
  log_retention_days: '90',
};

// ─── Mock Activity Logs ──────────────────────────────────────────────────────────
const actions = ['CREATE', 'UPDATE', 'DELETE', 'LOGIN', 'LOGOUT', 'RESET_PASSWORD'];
const targetTypes = ['team', 'user', 'dlp_pattern', 'settings', 'auth'];

function makeActivityLogs(): ActivityLog[] {
  const logs: ActivityLog[] = [];
  const usernames = mockUsers.map((u) => u.username);
  for (let i = 0; i < 20; i++) {
    const action = randomFrom(actions);
    const targetType = randomFrom(targetTypes);
    let changes: Record<string, { before: unknown; after: unknown }> | null = null;
    if (action === 'UPDATE') {
      changes = {
        enabled: { before: false, after: true },
        requests: { before: 50, after: 100 },
      };
    }
    logs.push({
      id: `act-${String(i + 1).padStart(3, '0')}`,
      user_id: randomFrom(mockUsers).id,
      username: randomFrom(usernames),
      action,
      target_type: targetType,
      target_id: `${targetType}-${Math.random().toString(36).slice(2, 8)}`,
      changes,
      ip_address: `10.0.1.${Math.floor(Math.random() * 50) + 1}`,
      timestamp: formatISO(subMinutes(now, Math.floor(Math.random() * 10080))),
    });
  }
  return logs.sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime());
}

const mockActivityLogs = makeActivityLogs();

// ─── In-memory state ─────────────────────────────────────────────────────────────
let teamsState = [...mockTeams];
let usersState = [...mockUsers];
let patternsState = [...mockDlpPatterns];
let settingsState = { ...mockSettings };
let incidentsState = [...mockIncidents];
let auditState = [...mockAuditLogs];
let activityState = [...mockActivityLogs];

function paginate<T>(items: T[], page = 1, pageSize = 20): PaginatedResponse<T> {
  const start = (page - 1) * pageSize;
  const end = start + pageSize;
  const sliced = items.slice(start, end);
  return {
    items: sliced,
    total: items.length,
    page,
    page_size: pageSize,
    total_pages: Math.ceil(items.length / pageSize),
  };
}

// ─── Mock API Export ─────────────────────────────────────────────────────────────
export const mockApi = {
  login: async (username: string, password: string): Promise<LoginResponse> => {
    await delay();
    const user = usersState.find((u) => u.username === username);
    if (!user || (password !== 'password' && password !== 'ChangeMe_At_First_Login_123!')) {
      throw { status: 401, message: 'Invalid username or password' };
    }
    if (!user.enabled) {
      throw { status: 423, message: 'Account locked', retry_after: 300 };
    }
    return { token: `mock-token-${username}-${Date.now()}`, token_type: 'bearer', force_password_change: user.force_password_change, user };
  },

  changePassword: async (_current: string, _newPass: string): Promise<void> => {
    await delay();
  },

  logout: async (): Promise<void> => {
    await delay(100);
  },

  getTeams: async (): Promise<Team[]> => {
    await delay();
    return [...teamsState];
  },

  createTeam: async (data: CreateTeamRequest): Promise<Team> => {
    await delay();
    const newTeam: Team = {
      id: Date.now(),
      ...data,
      created_by: 'current_user',
      created_at: formatISO(now),
      updated_at: formatISO(now),
    };
    teamsState = [newTeam, ...teamsState];
    return newTeam;
  },

  updateTeam: async (api_key: string, data: UpdateTeamRequest): Promise<Team> => {
    await delay();
    teamsState = teamsState.map((t) =>
      t.api_key === api_key ? { ...t, ...data, updated_at: formatISO(now) } : t
    );
    const updated = teamsState.find((t) => t.api_key === api_key);
    if (!updated) throw { status: 404, message: 'Team not found' };
    return updated;
  },

  deleteTeam: async (api_key: string): Promise<void> => {
    await delay();
    teamsState = teamsState.filter((t) => t.api_key !== api_key);
  },

  getIncidents: async (filters: IncidentFilters = {}): Promise<PaginatedResponse<DlpIncident>> => {
    await delay();
    let filtered = [...incidentsState];
    if (filters.team_name) {
      filtered = filtered.filter((i) => i.team_name === filters.team_name);
    }
    if (filters.severities && filters.severities.length > 0) {
      filtered = filtered.filter((i) => filters.severities!.includes(i.max_severity));
    }
    if (filters.incident_id) {
      filtered = filtered.filter((i) =>
        i.incident_id.toLowerCase().includes(filters.incident_id!.toLowerCase())
      );
    }
    if (filters.start_date) {
      filtered = filtered.filter((i) => new Date(i.timestamp) >= new Date(filters.start_date!));
    }
    if (filters.end_date) {
      filtered = filtered.filter((i) => new Date(i.timestamp) <= new Date(filters.end_date!));
    }
    return paginate(filtered, filters.page, filters.page_size);
  },

  exportIncidents: async (filters: IncidentFilters = {}): Promise<Blob> => {
    await delay();
    let filtered = [...incidentsState];
    if (filters.team_name) {
      filtered = filtered.filter((i) => i.team_name === filters.team_name);
    }
    const header = 'timestamp,incident_id,team_name,max_severity,patterns,source,message_len\n';
    const rows = filtered
      .map((i) =>
        `${i.timestamp},${i.incident_id},${i.team_name},${i.max_severity},"${i.patterns.join(';')}",${i.source},${i.message_len}`
      )
      .join('\n');
    return new Blob([header + rows], { type: 'text/csv' });
  },

  getAuditLog: async (filters: AuditFilters = {}): Promise<PaginatedResponse<AuditLog>> => {
    await delay();
    let filtered = [...auditState];
    if (filters.team_name) {
      filtered = filtered.filter((l) => l.team_name === filters.team_name);
    }
    if (filters.statuses && filters.statuses.length > 0) {
      filtered = filtered.filter((l) => filters.statuses!.includes(l.status));
    }
    if (filters.start_date) {
      filtered = filtered.filter((l) => new Date(l.timestamp) >= new Date(filters.start_date!));
    }
    if (filters.end_date) {
      filtered = filtered.filter((l) => new Date(l.timestamp) <= new Date(filters.end_date!));
    }
    return paginate(filtered, filters.page, filters.page_size);
  },

  exportAuditLog: async (filters: AuditFilters = {}): Promise<Blob> => {
    await delay();
    let filtered = [...auditState];
    if (filters.team_name) {
      filtered = filtered.filter((l) => l.team_name === filters.team_name);
    }
    const header = 'timestamp,team_name,model,status,latency_ms,dlp_flagged,tokens_used\n';
    const rows = filtered
      .map((l) =>
        `${l.timestamp},${l.team_name},${l.model},${l.status},${l.latency_ms},${l.dlp_flagged},${l.tokens_used}`
      )
      .join('\n');
    return new Blob([header + rows], { type: 'text/csv' });
  },

  getStatsSummary: async (): Promise<StatsSummary> => {
    await delay();
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const todayRequests = auditState.filter((l) => new Date(l.timestamp) >= today);
    return {
      total_requests_today: todayRequests.length + Math.floor(Math.random() * 50),
      dlp_blocks_today: todayRequests.filter((l) => l.status === 'blocked_dlp').length + Math.floor(Math.random() * 5),
      rate_limit_hits_today: todayRequests.filter((l) => l.status === 'blocked_rate_limit').length + Math.floor(Math.random() * 10),
      active_teams: teamsState.filter((t) => t.enabled).length,
    };
  },

  getStatsPerTeam: async (): Promise<PerTeamStat[]> => {
    await delay();
    const counts: Record<string, number> = {};
    const sixtyMinutesAgo = subMinutes(now, 60);
    auditState
      .filter((l) => new Date(l.timestamp) >= sixtyMinutesAgo)
      .forEach((l) => {
        counts[l.team_name] = (counts[l.team_name] || 0) + 1;
      });
    // Add some mock data to make chart interesting
    teamsState.forEach((t) => {
      if (!counts[t.team_name]) {
        counts[t.team_name] = Math.floor(Math.random() * 40) + 5;
      }
    });
    return Object.entries(counts).map(([team_name, count]) => ({ team_name, count }));
  },

  getDlpPatterns: async (): Promise<DlpPattern[]> => {
    await delay();
    return [...patternsState];
  },

  createDlpPattern: async (data: CreateDlpPatternRequest): Promise<DlpPattern> => {
    await delay();
    const newPattern: DlpPattern = {
      id: `pat-${Date.now()}`,
      ...data,
      created_by: 'current_user',
      created_at: formatISO(now),
    };
    patternsState = [newPattern, ...patternsState];
    return newPattern;
  },

  updateDlpPattern: async (name: string, data: UpdateDlpPatternRequest): Promise<DlpPattern> => {
    await delay();
    patternsState = patternsState.map((p) =>
      p.name === name ? { ...p, ...data } : p
    );
    const updated = patternsState.find((p) => p.name === name);
    if (!updated) throw { status: 404, message: 'Pattern not found' };
    return updated;
  },

  deleteDlpPattern: async (name: string): Promise<void> => {
    await delay();
    patternsState = patternsState.filter((p) => p.name !== name);
  },

  getSettings: async (): Promise<GatewaySettings> => {
    await delay();
    return { ...settingsState };
  },

  updateSettings: async (data: GatewaySettings): Promise<GatewaySettings> => {
    await delay();
    settingsState = { ...settingsState, ...data };
    return { ...settingsState };
  },

  getUsers: async (): Promise<User[]> => {
    await delay();
    return [...usersState];
  },

  createUser: async (data: CreateUserRequest): Promise<User> => {
    await delay();
    const newUser: User = {
      id: `usr-${Date.now()}`,
      username: data.username,
      email: data.email,
      full_name: data.full_name,
      role: data.role,
      enabled: true,
      force_password_change: true,
      last_login: null,
      created_by: 'current_user',
      created_at: formatISO(now),
      updated_at: formatISO(now),
    };
    usersState = [...usersState, newUser];
    return newUser;
  },

  updateUser: async (id: string, data: UpdateUserRequest): Promise<User> => {
    await delay();
    usersState = usersState.map((u) =>
      u.id === id ? { ...u, ...data, updated_at: formatISO(now) } : u
    );
    const updated = usersState.find((u) => u.id === id);
    if (!updated) throw { status: 404, message: 'User not found' };
    return updated;
  },

  resetPassword: async (_id: string): Promise<{ temp_password: string }> => {
    await delay();
    const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!@#$';
    const temp_password = Array.from({ length: 16 }, () => chars[Math.floor(Math.random() * chars.length)]).join('');
    return { temp_password };
  },

  getActivityLog: async (filters: ActivityFilters = {}): Promise<PaginatedResponse<ActivityLog>> => {
    await delay();
    let filtered = [...activityState];
    if (filters.username) {
      filtered = filtered.filter((l) =>
        l.username.toLowerCase().includes(filters.username!.toLowerCase())
      );
    }
    if (filters.action) {
      filtered = filtered.filter((l) =>
        l.action.toLowerCase().includes(filters.action!.toLowerCase())
      );
    }
    if (filters.target_type) {
      filtered = filtered.filter((l) => l.target_type === filters.target_type);
    }
    if (filters.start_date) {
      filtered = filtered.filter((l) => new Date(l.timestamp) >= new Date(filters.start_date!));
    }
    if (filters.end_date) {
      filtered = filtered.filter((l) => new Date(l.timestamp) <= new Date(filters.end_date!));
    }
    return paginate(filtered, filters.page, filters.page_size);
  },

  exportActivityLog: async (): Promise<Blob> => {
    await delay();
    const header = 'timestamp,username,action,target_type,target_id,ip_address\n';
    const rows = activityState
      .map((l) => `${l.timestamp},${l.username},${l.action},${l.target_type},${l.target_id},${l.ip_address}`)
      .join('\n');
    return new Blob([header + rows], { type: 'text/csv' });
  },

  getAvailableModels: async (): Promise<string[]> => {
    await delay(200);
    return ['phi3:mini', 'phi4-mini', 'llama3.2', 'llama3.1:8b', 'mistral', 'tinyllama'];
  },
};
