export type PlatformAdminUser = {
  id: number;
  email: string;
  name?: string | null;
  role: "admin";
  is_active: boolean;
  created_at?: string | null;
  deleted_at?: string | null;
  pending_registration?: boolean;
  mfa_enabled?: boolean;
};

export type PlatformAdminLoginResponse = {
  access_token: string;
  token_type: "bearer";
  user: PlatformAdminUser;
};

export type PlatformAdminDebugDateResponse = {
  enabled: boolean;
  simulated_date?: string | null;
  current_date: string;
};

export type PlatformAdminMfaStatusResponse = {
  enabled: boolean;
  pending: boolean;
  recovery_codes_remaining: number;
};

export type PlatformAdminMfaSetupResponse = {
  enabled: boolean;
  pending: boolean;
  secret: string;
  otpauth_uri: string;
  expires_at: string;
};

export type PlatformAdminMfaConfirmResponse = {
  enabled: boolean;
  pending: boolean;
  recovery_codes: string[];
};

export type PlatformAdminTenant = {
  id: number;
  slug: string;
  name: string;
  is_active: boolean;
  created_at?: string | null;
};

export type PlatformAdminStatisticsTenant = {
  id: number;
  slug: string;
  name: string;
  is_active: boolean;
  lifecycle_status?: "active" | "inactive" | "temporary_deleted" | string;
  created_at?: string | null;
  cancellation_request?: {
    id: number;
    status: string;
    reason_code?: string | null;
    requested_at?: string | null;
    effective_at?: string | null;
    deactivated_at?: string | null;
  } | null;
  package_code?: string | null;
  package_name?: string | null;
  billing_period?: string | null;
  subscription_status?: string | null;
  domain_count: number;
  verified_domain_count: number;
  domains: Array<{
    domain: string;
    verified: boolean;
    verified_at?: string | null;
    created_at?: string | null;
  }>;
  feature_flags: Record<string, unknown>;
  limits: Record<string, unknown>;
  usage: {
    questions: number;
    schema_queries: number;
    trained_chars: number;
    storage_bytes: number;
    file_bytes: number;
    database_bytes: number;
    qdrant_bytes: number;
    qdrant_points: number;
    qdrant_vectors: number;
    users: number;
    knowledge_bases: number;
    training_runs: number;
    training_items: number;
    training_completed: number;
    training_failed: number;
    avg_latency_ms: number;
    last_query_at?: string | null;
    last_training_at?: string | null;
  };
};

export type PlatformAdminStatisticsResponse = {
  summary: {
    tenants: number;
    active_tenants: number;
    questions: number;
    schema_queries: number;
    trained_chars: number;
    storage_bytes: number;
    file_bytes: number;
    database_bytes: number;
    qdrant_bytes: number;
    qdrant_points: number;
    qdrant_vectors: number;
    users: number;
    knowledge_bases: number;
    training_runs: number;
    training_items: number;
    domains: number;
    verified_domains: number;
    paid_this_year_cents: number;
    expected_annual_revenue_cents: number;
    expected_average_monthly_revenue_cents: number;
  };
  tenants: PlatformAdminStatisticsTenant[];
};

export type PlatformAdminAuditTrailItem = {
  id: number;
  created_at: string;
  user_id?: number | null;
  actor_user_id?: number | null;
  actor_type: string;
  action: string;
  event_name?: string | null;
  outcome?: string | null;
  target_type?: string | null;
  target_id?: string | null;
  correlation_id?: string | null;
  details: Record<string, unknown>;
  ip?: string | null;
  user_agent?: string | null;
  actor_email?: string | null;
  actor_email_masked?: string | null;
  actor_email_hash?: string | null;
  actor_name?: string | null;
  target_user_email_masked?: string | null;
  target_user_name?: string | null;
  target_user_settings?: Record<string, unknown> | null;
  title: string;
  summary: string;
};

export type PlatformAdminAuditTrailResponse = {
  items: PlatformAdminAuditTrailItem[];
  limit: number;
  next_cursor?: string | null;
  tenant: {
    id: number;
    slug: string;
    name: string;
    is_active: boolean;
    timezone?: string | null;
  };
};

export type PlatformAdminTenantStatisticsDetail = {
  tenant: {
    id: number;
    slug: string;
    name: string;
    is_active: boolean;
    created_at?: string | null;
    updated_at?: string | null;
  };
  billing: {
    package_code?: string | null;
    package_name?: string | null;
    billing_period?: string | null;
    status?: string | null;
    current_period?: {
      start_iso?: string | null;
      end_iso?: string | null;
    };
    paid_total_cents: number;
    paid_invoice_count: number;
  };
  domains: Array<{
    domain: string;
    verified: boolean;
    verified_at?: string | null;
    created_at?: string | null;
  }>;
  feature_flags: Record<string, unknown>;
  limits: Record<string, unknown>;
  usage: PlatformAdminStatisticsTenant["usage"];
  monthly: Array<{
    month: string;
    questions: number;
    training_chars: number;
    training_runs: number;
    usage_hours: number;
  }>;
};

export type PlatformAdminSecurityMonitoringResponse = {
  summary: {
    window_hours: number;
    failed_login: number;
    failed_refresh: number;
    failed_logout: number;
    rate_limited: number;
    suspicious_fingerprint: number;
    risk_events_total: number;
  };
  metrics_summary: {
    request_count: number;
    request_error_count: number;
    unhandled_error_count: number;
    rate_limit_hit_count: number;
    auth_failure_count: number;
    outbox_failed_count: number;
    request_latency_avg_ms: number;
    request_latency_max_ms: number;
    request_latency_last_ms: number;
  };
  alerts: Array<{
    id: number;
    key: string;
    category: string;
    severity: "high" | "medium" | "low";
    title: string;
    signal: string;
    value: number;
    hit_count: number;
    status: "open" | "acknowledged";
    first_seen_at?: string | null;
    last_seen_at?: string | null;
    acknowledged_at?: string | null;
    acknowledged_by?: number | null;
  }>;
  events: Array<{
    scope: "platform_admin" | "tenant";
    tenant: string | null;
    host: string | null;
    action: string;
    outcome: string | null;
    ip: string | null;
    severity: "high" | "medium" | "low";
    created_at?: string | null;
    possible_test_traffic?: boolean;
  }>;
  tenant_hotspots: Array<{
    tenant: string;
    host: string;
    risk_events: number;
  }>;
  attack_signals: Array<{
    severity: "high" | "medium" | "low";
    signal: string;
    value: number;
  }>;
  top_sources: Array<{
    source_hash: string;
    risk_events: number;
  }>;
  signup_watch: {
    new_tenants_24h: number;
    new_tenants_7d: number;
    new_tenants_30d: number;
    new_tenants_without_training_7d: number;
  };
  duplicate_users: Array<{
    email: string;
    tenants: string[];
    tenant_count: number;
  }>;
  concurrent_ip_anomalies: Array<{
    tenant: string;
    user_id: number;
    distinct_ip_count_24h: number;
  }>;
  banned_ips: Array<{
    ip: string;
    reason?: string | null;
    created_at?: string | null;
    expires_at?: string | null;
    active: boolean;
  }>;
  ai_assessment: string;
  event_stream_summary: Array<{
    event: string;
    category: "auth" | "security" | "business" | "system" | "other";
    count: number;
    status: "active" | "not_detected";
  }>;
  alert_rule_results: Array<{
    rule_id: string;
    priority: "P1" | "P2" | "P3";
    title: string;
    wake_up: boolean;
    status: "triggered" | "ok" | "unavailable";
    value?: number | null;
    threshold?: number | null;
    window_minutes?: number | null;
    reason?: string | null;
  }>;
  monitoring_metrics: Array<{
    domain: "application" | "auth_security" | "infrastructure" | "business";
    key: string;
    label: string;
    value?: number | null;
    unit?: string | null;
    status: "available" | "unavailable";
    reason?: string | null;
    details?: Array<Record<string, unknown>> | null;
  }>;
  mvp_readiness: {
    status: "green" | "yellow" | "red";
    score_percent: number;
    configured_checks: number;
    total_checks: number;
    missing_checks: number;
    triggered_checks: number;
    checks: Array<{
      id: string;
      label: string;
      configured: boolean;
      runtime_status: "ok" | "triggered";
      detail?: string | null;
    }>;
  };
  dashboards: Array<{
    id: "system_health" | "security" | "business_product";
    title: string;
    order: number;
    items: Array<{
      label: string;
      status: "available" | "unavailable";
      value?: number | null;
      unit?: string | null;
      reason?: string | null;
      metric_key?: string;
      details?: Array<Record<string, unknown>>;
    }>;
  }>;
};
