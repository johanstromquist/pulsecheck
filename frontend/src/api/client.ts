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
