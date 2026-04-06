export interface ComponentStatus {
  name: string;
  label: string;
  available: boolean;
  admin_url: string | null;
}

export interface OrgMetrics {
  id: string;
  name: string;
  slug: string;
  plan: string;
  is_active: boolean;
  member_count: number;
  story_count: number;
  feature_count: number;
  story_limit: number;
  member_limit: number;
  story_usage_pct: number;
  member_usage_pct: number;
  warning: boolean;
  created_at: string;
}

export interface AdminSession {
  access_token: string;
  id_token: string;
  expires_at: number; // Unix timestamp ms
}

export interface ConfigEntry {
  value: string | null;
  is_secret: boolean;
  is_set?: boolean; // only present when is_secret=true
}

export type ConfigMap = Record<string, ConfigEntry>;
