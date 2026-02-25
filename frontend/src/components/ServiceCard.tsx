import { useEffect, useState } from "react";
import type { Service, HealthCheck } from "../api/client";
import { fetchHealthChecks } from "../api/client";

interface ServiceCardProps {
  service: Service;
}

const STATUS_COLORS: Record<string, string> = {
  healthy: "bg-green-500",
  degraded: "bg-yellow-500",
  down: "bg-red-500",
};

const STATUS_LABELS: Record<string, string> = {
  healthy: "Healthy",
  degraded: "Degraded",
  down: "Down",
};

function formatTime(iso: string): string {
  return new Date(iso).toLocaleString();
}

export default function ServiceCard({ service }: ServiceCardProps) {
  const [latestCheck, setLatestCheck] = useState<HealthCheck | null>(null);

  useEffect(() => {
    fetchHealthChecks(service.id)
      .then((checks) => {
        if (checks.length > 0) setLatestCheck(checks[0]);
      })
      .catch(() => {});
  }, [service.id]);

  const status = latestCheck?.status ?? "unknown";
  const dotColor = STATUS_COLORS[status] ?? "bg-gray-400";
  const label = STATUS_LABELS[status] ?? "Unknown";

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-lg font-semibold text-gray-900">{service.name}</h3>
        <span className="flex items-center gap-1.5 text-sm text-gray-600">
          <span className={`inline-block h-3 w-3 rounded-full ${dotColor}`} />
          {label}
        </span>
      </div>

      <p className="mb-3 truncate text-sm text-gray-500" title={service.url}>
        {service.url}
      </p>

      <div className="flex items-center justify-between text-xs text-gray-400">
        <span>
          {latestCheck
            ? `Last check: ${formatTime(latestCheck.checked_at)}`
            : "No checks yet"}
        </span>
        {latestCheck?.response_time_ms != null && (
          <span>{latestCheck.response_time_ms} ms</span>
        )}
      </div>
    </div>
  );
}
