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
