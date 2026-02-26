import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import type {
  StatusPageData,
  StatusPageServiceData,
  StatusPageIncident,
} from "../api/client";
import { fetchStatusPage } from "../api/client";

const STATUS_COLORS: Record<string, string> = {
  healthy: "bg-green-500",
  degraded: "bg-yellow-500",
  down: "bg-red-500",
  unknown: "bg-gray-400",
};

const STATUS_LABELS: Record<string, string> = {
  healthy: "Operational",
  degraded: "Degraded",
  down: "Down",
  unknown: "Unknown",
};

const INCIDENT_STATUS_COLORS: Record<string, string> = {
  investigating: "bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-400",
  identified: "bg-orange-100 text-orange-800 dark:bg-orange-900/40 dark:text-orange-400",
  monitoring: "bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-400",
  resolved: "bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-400",
};

const SEVERITY_COLORS: Record<string, string> = {
  minor: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/40 dark:text-yellow-400",
  major: "bg-orange-100 text-orange-800 dark:bg-orange-900/40 dark:text-orange-400",
  critical: "bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-400",
};

const OVERALL_BANNER: Record<
  string,
  { bg: string; text: string; border: string }
> = {
  "All Systems Operational": {
    bg: "bg-green-50 dark:bg-green-900/30",
    text: "text-green-800 dark:text-green-400",
    border: "border-green-200 dark:border-green-800",
  },
  "Partial Outage": {
    bg: "bg-yellow-50 dark:bg-yellow-900/30",
    text: "text-yellow-800 dark:text-yellow-400",
    border: "border-yellow-200 dark:border-yellow-800",
  },
  "Major Outage": {
    bg: "bg-red-50 dark:bg-red-900/30",
    text: "text-red-800 dark:text-red-400",
    border: "border-red-200 dark:border-red-800",
  },
};

function formatTime(iso: string): string {
  return new Date(iso).toLocaleString();
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString();
}

function UptimeBar({
  dailyUptime,
}: {
  dailyUptime: { date: string; uptime: number | null }[];
}) {
  return (
    <div className="flex gap-px">
      {dailyUptime.map((day) => {
        let color = "bg-gray-200 dark:bg-gray-600";
        if (day.uptime !== null) {
          if (day.uptime >= 99) color = "bg-green-500";
          else if (day.uptime >= 95) color = "bg-yellow-500";
          else if (day.uptime >= 80) color = "bg-orange-500";
          else color = "bg-red-500";
        }
        return (
          <div
            key={day.date}
            className={`h-8 flex-1 rounded-sm ${color}`}
            title={`${day.date}: ${day.uptime !== null ? `${day.uptime}%` : "No data"}`}
          />
        );
      })}
    </div>
  );
}

function ServiceRow({ service }: { service: StatusPageServiceData }) {
  const dotColor = STATUS_COLORS[service.current_status] ?? "bg-gray-400";
  const label = STATUS_LABELS[service.current_status] ?? "Unknown";

  return (
    <div className="border-b border-gray-100 py-4 last:border-0 dark:border-gray-700">
      <div className="mb-2 flex items-center justify-between">
        <span className="font-medium text-gray-900 dark:text-white">{service.name}</span>
        <span className="flex items-center gap-1.5 text-sm">
          <span className={`inline-block h-2 w-2 rounded-full ${dotColor}`} />
          <span
            className={
              service.current_status === "healthy"
                ? "text-green-700 dark:text-green-400"
                : service.current_status === "down"
                  ? "text-red-700 dark:text-red-400"
                  : "text-yellow-700 dark:text-yellow-400"
            }
          >
            {label}
          </span>
        </span>
      </div>
      <UptimeBar dailyUptime={service.daily_uptime} />
      <div className="mt-1 flex justify-between text-xs text-gray-400 dark:text-gray-500">
        <span>90 days ago</span>
        <span>
          {service.uptime_90d !== null
            ? `${service.uptime_90d.toFixed(2)}% uptime`
            : "N/A"}
        </span>
        <span>Today</span>
      </div>
    </div>
  );
}

function IncidentCard({ incident }: { incident: StatusPageIncident }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800">
      <div
        className="flex cursor-pointer items-start justify-between"
        onClick={() => setExpanded(!expanded)}
      >
        <div>
          <div className="mb-1 flex items-center gap-2">
            <h3 className="font-medium text-gray-900 dark:text-white">{incident.title}</h3>
            <span
              className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium capitalize ${SEVERITY_COLORS[incident.severity] ?? ""}`}
            >
              {incident.severity}
            </span>
            <span
              className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium capitalize ${INCIDENT_STATUS_COLORS[incident.status] ?? ""}`}
            >
              {incident.status}
            </span>
          </div>
          <p className="text-xs text-gray-400 dark:text-gray-500">
            {formatDate(incident.started_at)}
            {incident.resolved_at && ` - ${formatDate(incident.resolved_at)}`}
          </p>
        </div>
        <span className="text-xs text-gray-400 dark:text-gray-500">
          {expanded ? "Hide" : "Show"} updates
        </span>
      </div>

      {expanded && incident.updates.length > 0 && (
        <div className="mt-3 space-y-2 border-t border-gray-100 pt-3 dark:border-gray-700">
          {incident.updates.map((update) => (
            <div key={update.id} className="flex gap-2 text-sm">
              <span
                className={`mt-1.5 inline-block h-2 w-2 flex-shrink-0 rounded-full ${
                  update.status === "resolved"
                    ? "bg-green-500"
                    : update.status === "monitoring"
                      ? "bg-blue-500"
                      : update.status === "identified"
                        ? "bg-orange-500"
                        : "bg-red-500"
                }`}
              />
              <div>
                <p className="text-gray-700 dark:text-gray-300">{update.message}</p>
                <p className="text-xs text-gray-400 dark:text-gray-500">
                  {formatTime(update.created_at)} - {update.created_by}
                </p>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function StatusPage() {
  const [data, setData] = useState<StatusPageData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchStatusPage()
      .then(setData)
      .catch((err) =>
        setError(err instanceof Error ? err.message : "Failed to load"),
      )
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-8">
        <p className="text-gray-500 dark:text-gray-400">Loading status page...</p>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-8">
        <div className="rounded-lg border border-red-200 bg-red-50 p-6 text-center text-red-600 dark:border-red-800 dark:bg-red-900/30 dark:text-red-400">
          {error ?? "Failed to load status page"}
        </div>
      </div>
    );
  }

  const bannerStyle = OVERALL_BANNER[data.overall_status] ??
    OVERALL_BANNER["All Systems Operational"];

  return (
    <div className="mx-auto max-w-3xl px-4 py-8">
      {/* Header */}
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
          PulseCheck Status
        </h1>
        <div className="flex items-center gap-3">
          <Link to="/" className="text-sm text-blue-600 hover:underline dark:text-blue-400">
            Dashboard
          </Link>
          <Link
            to="/incidents"
            className="text-sm text-blue-600 hover:underline dark:text-blue-400"
          >
            Incidents
          </Link>
        </div>
      </div>

      {/* Overall status banner */}
      <div
        className={`mb-6 rounded-lg border p-4 text-center ${bannerStyle.bg} ${bannerStyle.border}`}
      >
        <p className={`text-lg font-semibold ${bannerStyle.text}`}>
          {data.overall_status}
        </p>
      </div>

      {/* Services */}
      <div className="mb-8 rounded-lg border border-gray-200 bg-white p-6 dark:border-gray-700 dark:bg-gray-800">
        <h2 className="mb-4 text-lg font-semibold text-gray-800 dark:text-gray-200">Services</h2>
        {data.services.length === 0 ? (
          <p className="text-sm text-gray-400 dark:text-gray-500">No services configured.</p>
        ) : (
          data.services.map((svc) => (
            <ServiceRow key={svc.id} service={svc} />
          ))
        )}
      </div>

      {/* Active incidents */}
      {data.active_incidents.length > 0 && (
        <div className="mb-8">
          <h2 className="mb-4 text-lg font-semibold text-gray-800 dark:text-gray-200">
            Active Incidents
          </h2>
          <div className="space-y-3">
            {data.active_incidents.map((inc) => (
              <IncidentCard key={inc.id} incident={inc} />
            ))}
          </div>
        </div>
      )}

      {/* Recent incidents (last 14 days) */}
      <div className="mb-8">
        <h2 className="mb-4 text-lg font-semibold text-gray-800 dark:text-gray-200">
          Past Incidents (Last 14 Days)
        </h2>
        {data.recent_incidents.length === 0 ? (
          <div className="rounded-lg border border-gray-200 bg-white p-6 text-center text-sm text-gray-400 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-500">
            No incidents in the last 14 days.
          </div>
        ) : (
          <div className="space-y-3">
            {data.recent_incidents.map((inc) => (
              <IncidentCard key={inc.id} incident={inc} />
            ))}
          </div>
        )}
      </div>

      <div className="text-center text-xs text-gray-400 dark:text-gray-500">
        Powered by PulseCheck
      </div>
    </div>
  );
}
