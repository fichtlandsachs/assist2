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
  last_login_at: string | null;
  last_active_user: string | null;
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

export interface OrgJiraSettings {
  base_url: string;
  user: string;
  api_token_set: boolean;
}

export interface OrgConfluenceSettings {
  base_url: string;
  user: string;
  api_token_set: boolean;
  default_space_key: string;
  default_parent_page_id: string;
}

export interface OrgSSOSettings {
  enabled: boolean;
  client_id: string;
  client_secret_set: boolean;
}

export interface UserWithOrgs {
  id: string;
  email: string;
  display_name: string;
  is_active: boolean;
  is_superuser: boolean;
  created_at: string;
  organizations: { id: string; name: string; slug: string }[];
}

export interface OrgIntegrationSettings {
  jira: OrgJiraSettings;
  confluence: OrgConfluenceSettings;
  github: OrgSSOSettings;
  atlassian: OrgSSOSettings;
}
