export type Role = 'superadmin' | 'admin' | 'analyst' | 'readonly';

export interface User {
  id: string;
  username: string;
  email: string;
  full_name: string;
  role: Role;
  enabled: boolean;
  force_password_change: boolean;
  last_login: string | null;
  created_by: string;
  created_at: string;
  updated_at: string;
}

export interface Team {
  id: number;
  api_key: string;
  team_name: string;
  model: string;
  requests: number;
  window_sec: number;
  enabled: boolean;
  system_prompt: string;
  created_by: string;
  created_at: string;
  updated_at: string;
}

export interface DlpIncident {
  id: string;
  incident_id: string;
  api_key: string;
  team_name: string;
  client_ip: string;
  patterns: string[];
  severities: string[];
  max_severity: string;
  match_counts: Record<string, number>;
  message_len: number;
  source: string;
  timestamp: string;
}

export interface AuditLog {
  id: string;
  api_key: string;
  team_name: string;
  model: string;
  status: string;
  prompt_hash: string;
  response_status: number;
  latency_ms: number;
  auth_ms: number;
  dlp_ms: number;
  inject_ms: number;
  vllm_ms: number;
  dlp_flagged: boolean;
  incident_id: string | null;
  tokens_used: number;
  client_ip: string;
  timestamp: string;
}

export interface DlpPattern {
  id: string;
  name: string;
  pattern: string;
  severity: string;
  enabled: boolean;
  created_by: string;
  created_at: string;
}

export type GatewaySettings = Record<string, string>;

export interface ActivityLog {
  id: string;
  user_id: string;
  username: string;
  action: string;
  target_type: string;
  target_id: string;
  changes: Record<string, { before: unknown; after: unknown }> | null;
  ip_address: string;
  timestamp: string;
}

export interface StatsSummary {
  total_requests_today: number;
  dlp_blocks_today: number;
  rate_limit_hits_today: number;
  active_teams: number;
}

export interface PerTeamStat {
  team_name: string;
  count: number;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface LoginResponse {
  token: string;
  token_type: string;
  force_password_change: boolean;
  user: User;
}

export interface ChangePasswordRequest {
  current_password: string;
  new_password: string;
}

export interface CreateTeamRequest {
  api_key: string;
  team_name: string;
  model: string;
  requests: number;
  window_sec: number;
  enabled: boolean;
  system_prompt: string;
}

export interface UpdateTeamRequest {
  team_name?: string;
  model?: string;
  requests?: number;
  window_sec?: number;
  enabled?: boolean;
  system_prompt?: string;
}

export interface CreateUserRequest {
  username: string;
  full_name: string;
  email: string;
  role: Role;
  temp_password: string;
}

export interface UpdateUserRequest {
  full_name?: string;
  email?: string;
  role?: Role;
  enabled?: boolean;
}

export interface CreateDlpPatternRequest {
  name: string;
  pattern: string;
  severity: string;
  enabled: boolean;
}

export interface UpdateDlpPatternRequest {
  pattern?: string;
  severity?: string;
  enabled?: boolean;
}

export interface IncidentFilters {
  start_date?: string;
  end_date?: string;
  severities?: string[];
  team_name?: string;
  incident_id?: string;
  page?: number;
  page_size?: number;
}

export interface AuditFilters {
  start_date?: string;
  end_date?: string;
  team_name?: string;
  statuses?: string[];
  page?: number;
  page_size?: number;
}

export interface ActivityFilters {
  start_date?: string;
  end_date?: string;
  username?: string;
  action?: string;
  target_type?: string;
  page?: number;
  page_size?: number;
}
