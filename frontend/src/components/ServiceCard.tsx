import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import type { Service, HealthCheck } from "../api/client";
import { fetchHealthChecks } from "../api/client";
import type { HealthCheckMessage } from "../hooks/useWebSocket";

interface ServiceCardProps {
  service: Service;
  realtimeCheck: HealthCheckMessage | null;
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

export default function ServiceCard({ service, realtimeCheck }: ServiceCardProps) {
  const [latestCheck, setLatestCheck] = useState<HealthCheck | null>(null);

  useEffect(() => {
    fetchHealthChecks(service.id)
      .then((checks) => {
        if (checks.length > 0) setLatestCheck(checks[0]);
      })
      .catch(() => {});
  }, [service.id]);

  // Use realtime data if it's newer than the fetched check
  const displayStatus = realtimeCheck?.status ?? latestCheck?.status ?? "unknown";
  const displayTime = realtimeCheck?.checked_at ?? latestCheck?.checked_at ?? null;
  const displayResponseTime =
    realtimeCheck?.response_time_ms ?? latestCheck?.response_time_ms ?? null;

  const dotColor = STATUS_COLORS[displayStatus] ?? "bg-gray-400";
  const label = STATUS_LABELS[displayStatus] ?? "Unknown";

  return (
    <Link
      to={`/services/${service.id}`}
      className="block rounded-lg border border-gray-200 bg-white p-5 shadow-sm transition-shadow hover:shadow-md dark:border-gray-700 dark:bg-gray-800"
    >
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white">{service.name}</h3>
        <span className="flex items-center gap-1.5 text-sm text-gray-600 dark:text-gray-300">
          <span className={`inline-block h-3 w-3 rounded-full ${dotColor}`} />
          {label}
        </span>
      </div>

      <p className="mb-3 truncate text-sm text-gray-500 dark:text-gray-400" title={service.url}>
        {service.url}
      </p>

      <div className="flex items-center justify-between text-xs text-gray-400 dark:text-gray-500">
        <span>
          {displayTime
            ? `Last check: ${formatTime(displayTime)}`
            : "No checks yet"}
        </span>
        {displayResponseTime != null && (
          <span>{displayResponseTime} ms</span>
        )}
      </div>
    </Link>
  );
}
