const BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export interface Service {
  id: string;
  name: string;
  url: string;
  check_interval_seconds: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface HealthCheck {
  id: string;
  service_id: string;
  status: "healthy" | "degraded" | "down";
  response_time_ms: number | null;
  status_code: number | null;
  error_message: string | null;
  checked_at: string;
}

export interface CreateServicePayload {
  name: string;
  url: string;
  check_interval_seconds?: number;
}

export async function fetchServices(
  limit = 100,
  offset = 0,
): Promise<Service[]> {
  const res = await fetch(
    `${BASE_URL}/api/v1/services?limit=${limit}&offset=${offset}`,
  );
  if (!res.ok) throw new Error(`Failed to fetch services: ${res.statusText}`);
  return res.json();
}

export async function createService(
  payload: CreateServicePayload,
): Promise<Service> {
  const res = await fetch(`${BASE_URL}/api/v1/services`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(
      body?.detail || `Failed to create service: ${res.statusText}`,
    );
  }
  return res.json();
}

export interface MetricsBucket {
  timestamp: string;
  avg_response_time_ms: number | null;
  min_response_time_ms: number | null;
  max_response_time_ms: number | null;
  check_count: number;
  healthy_count: number;
  degraded_count: number;
  down_count: number;
  uptime_percentage: number;
}

export interface UptimePeriod {
  period: string;
  uptime_percentage: number | null;
  total_checks: number;
}

export type Period = "1h" | "6h" | "24h" | "7d" | "30d";

export async function fetchHealthChecks(
  serviceId: string,
): Promise<HealthCheck[]> {
  const res = await fetch(
    `${BASE_URL}/api/v1/services/${serviceId}/checks`,
  );
  if (!res.ok)
    throw new Error(`Failed to fetch health checks: ${res.statusText}`);
  return res.json();
}

export async function fetchService(serviceId: string): Promise<Service> {
  const res = await fetch(`${BASE_URL}/api/v1/services/${serviceId}`);
  if (!res.ok) throw new Error(`Failed to fetch service: ${res.statusText}`);
  return res.json();
}

export async function fetchMetrics(
  serviceId: string,
  period: Period = "24h",
): Promise<MetricsBucket[]> {
  const res = await fetch(
    `${BASE_URL}/api/v1/services/${serviceId}/metrics?period=${period}`,
  );
  if (!res.ok) throw new Error(`Failed to fetch metrics: ${res.statusText}`);
  return res.json();
}

export async function fetchUptime(
  serviceId: string,
): Promise<UptimePeriod[]> {
  const res = await fetch(
    `${BASE_URL}/api/v1/services/${serviceId}/uptime`,
  );
  if (!res.ok) throw new Error(`Failed to fetch uptime: ${res.statusText}`);
  return res.json();
}

export interface SSLCertificate {
  id: string;
  service_id: string;
  issuer: string;
  subject: string;
  serial_number: string;
  not_before: string;
  not_after: string;
  days_until_expiry: number;
  last_checked_at: string;
  created_at: string;
  updated_at: string;
}

export async function fetchSSLCertificate(
  serviceId: string,
): Promise<SSLCertificate | null> {
  const res = await fetch(
    `${BASE_URL}/api/v1/services/${serviceId}/ssl`,
  );
  if (res.status === 404) return null;
  if (!res.ok)
    throw new Error(`Failed to fetch SSL certificate: ${res.statusText}`);
  return res.json();
}

// --- Incident types and API ---

export type IncidentSeverity = "minor" | "major" | "critical";
export type IncidentStatusType =
  | "investigating"
  | "identified"
  | "monitoring"
  | "resolved";

export interface IncidentUpdateEntry {
  id: string;
  incident_id: string;
  message: string;
  status: IncidentStatusType;
  created_by: string;
  created_at: string;
}

export interface Incident {
  id: string;
  title: string;
  description: string | null;
  severity: IncidentSeverity;
  status: IncidentStatusType;
  affected_service_ids: string[];
  started_at: string;
  resolved_at: string | null;
  created_by: string;
  created_at: string;
  updated_at: string;
}

export interface IncidentDetail extends Incident {
  updates: IncidentUpdateEntry[];
}

export interface CreateIncidentPayload {
  title: string;
  description?: string;
  severity: IncidentSeverity;
  affected_service_ids?: string[];
  created_by?: string;
}

export interface CreateIncidentUpdatePayload {
  message: string;
  status: IncidentStatusType;
  created_by?: string;
}

export async function fetchIncidents(params?: {
  status?: IncidentStatusType;
  severity?: IncidentSeverity;
  limit?: number;
  offset?: number;
}): Promise<Incident[]> {
  const searchParams = new URLSearchParams();
  if (params?.status) searchParams.set("status", params.status);
  if (params?.severity) searchParams.set("severity", params.severity);
  if (params?.limit) searchParams.set("limit", String(params.limit));
  if (params?.offset) searchParams.set("offset", String(params.offset));
  const qs = searchParams.toString();
  const res = await fetch(
    `${BASE_URL}/api/v1/incidents${qs ? `?${qs}` : ""}`,
  );
  if (!res.ok) throw new Error(`Failed to fetch incidents: ${res.statusText}`);
  return res.json();
}

export async function fetchIncident(id: string): Promise<IncidentDetail> {
  const res = await fetch(`${BASE_URL}/api/v1/incidents/${id}`);
  if (!res.ok) throw new Error(`Failed to fetch incident: ${res.statusText}`);
  return res.json();
}

export async function createIncident(
  payload: CreateIncidentPayload,
): Promise<Incident> {
  const res = await fetch(`${BASE_URL}/api/v1/incidents`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(
      body?.detail || `Failed to create incident: ${res.statusText}`,
    );
  }
  return res.json();
}

export async function addIncidentUpdate(
  incidentId: string,
  payload: CreateIncidentUpdatePayload,
): Promise<IncidentUpdateEntry> {
  const res = await fetch(
    `${BASE_URL}/api/v1/incidents/${incidentId}/updates`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  );
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(
      body?.detail || `Failed to add update: ${res.statusText}`,
    );
  }
  return res.json();
}

export async function resolveIncident(id: string): Promise<Incident> {
  const res = await fetch(`${BASE_URL}/api/v1/incidents/${id}/resolve`, {
    method: "POST",
  });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(
      body?.detail || `Failed to resolve incident: ${res.statusText}`,
    );
  }
  return res.json();
}

// --- Status Page API ---

export interface StatusPageServiceData {
  id: string;
  name: string;
  url: string;
  current_status: "healthy" | "degraded" | "down" | "unknown";
  uptime_90d: number | null;
  daily_uptime: { date: string; uptime: number | null }[];
}

export interface StatusPageIncident {
  id: string;
  title: string;
  description: string | null;
  severity: IncidentSeverity;
  status: IncidentStatusType;
  affected_service_ids: string[];
  started_at: string;
  resolved_at: string | null;
  created_at: string;
  updates: {
    id: string;
    message: string;
    status: IncidentStatusType;
    created_by: string;
    created_at: string;
  }[];
}

export interface StatusPageData {
  overall_status: string;
  services: StatusPageServiceData[];
  active_incidents: StatusPageIncident[];
  recent_incidents: StatusPageIncident[];
}

export async function fetchStatusPage(): Promise<StatusPageData> {
  const res = await fetch(`${BASE_URL}/api/v1/status-page`);
  if (!res.ok)
    throw new Error(`Failed to fetch status page: ${res.statusText}`);
  return res.json();
}
