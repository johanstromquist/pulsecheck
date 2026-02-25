import { useEffect, useState, useCallback } from "react";
import { useParams, Link } from "react-router-dom";
import {
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Area,
  AreaChart,
} from "recharts";
import type {
  Service,
  HealthCheck,
  MetricsBucket,
  UptimePeriod,
  Period,
  SSLCertificate,
  ByRegionResponse,
  RegionCheckResult,
} from "../api/client";
import {
  fetchService,
  fetchHealthChecks,
  fetchMetrics,
  fetchUptime,
  fetchSSLCertificate,
  fetchChecksByRegion,
} from "../api/client";

const PERIODS: { value: Period; label: string }[] = [
  { value: "1h", label: "1h" },
  { value: "6h", label: "6h" },
  { value: "24h", label: "24h" },
  { value: "7d", label: "7d" },
  { value: "30d", label: "30d" },
];

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

function formatChartTime(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

/* ---------- Skeleton components ---------- */

function SkeletonBlock({ className = "" }: { className?: string }) {
  return (
    <div className={`animate-pulse rounded bg-gray-200 ${className}`} />
  );
}

function ChartSkeleton() {
  return (
    <div className="rounded-lg border border-gray-200 bg-white p-5">
      <SkeletonBlock className="mb-4 h-5 w-40" />
      <SkeletonBlock className="h-64 w-full" />
    </div>
  );
}

function TableSkeleton() {
  return (
    <div className="rounded-lg border border-gray-200 bg-white p-5">
      <SkeletonBlock className="mb-4 h-5 w-36" />
      {Array.from({ length: 5 }).map((_, i) => (
        <SkeletonBlock key={i} className="mb-2 h-8 w-full" />
      ))}
    </div>
  );
}

/* ---------- Sub-components ---------- */

function UptimeBadge({
  period,
  percentage,
}: {
  period: string;
  percentage: number | null;
}) {
  let color = "bg-gray-100 text-gray-500";
  if (percentage !== null) {
    if (percentage >= 99) color = "bg-green-100 text-green-800";
    else if (percentage >= 95) color = "bg-yellow-100 text-yellow-800";
    else color = "bg-red-100 text-red-800";
  }

  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-3 py-1 text-xs font-medium ${color}`}
    >
      {period}:{" "}
      {percentage !== null ? `${percentage.toFixed(2)}%` : "N/A"}
    </span>
  );
}

function PeriodSelector({
  selected,
  onChange,
}: {
  selected: Period;
  onChange: (p: Period) => void;
}) {
  return (
    <div className="flex gap-1">
      {PERIODS.map((p) => (
        <button
          key={p.value}
          onClick={() => onChange(p.value)}
          className={`rounded px-3 py-1.5 text-xs font-medium transition-colors ${
            selected === p.value
              ? "bg-blue-600 text-white"
              : "bg-gray-100 text-gray-600 hover:bg-gray-200"
          }`}
        >
          {p.label}
        </button>
      ))}
    </div>
  );
}

function ResponseTimeChart({ data }: { data: MetricsBucket[] }) {
  if (data.length === 0) {
    return (
      <div className="rounded-lg border border-gray-200 bg-white p-5">
        <h3 className="mb-4 text-sm font-semibold text-gray-700">
          Response Time
        </h3>
        <div className="flex h-64 items-center justify-center text-sm text-gray-400">
          No data available for this period.
        </div>
      </div>
    );
  }

  const chartData = data.map((b) => ({
    time: formatChartTime(b.timestamp),
    avg: b.avg_response_time_ms,
    min: b.min_response_time_ms,
    max: b.max_response_time_ms,
  }));

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-5">
      <h3 className="mb-4 text-sm font-semibold text-gray-700">
        Response Time (ms)
      </h3>
      <ResponsiveContainer width="100%" height={280}>
        <AreaChart data={chartData}>
          <defs>
            <linearGradient id="minMaxGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.15} />
              <stop offset="95%" stopColor="#3b82f6" stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
          <XAxis
            dataKey="time"
            tick={{ fontSize: 11, fill: "#9ca3af" }}
            tickLine={false}
          />
          <YAxis
            tick={{ fontSize: 11, fill: "#9ca3af" }}
            tickLine={false}
            axisLine={false}
            unit=" ms"
          />
          <Tooltip
            contentStyle={{
              fontSize: 12,
              borderRadius: 8,
              border: "1px solid #e5e7eb",
            }}
            formatter={(value: unknown) =>
              value != null ? [`${value} ms`] : ["N/A"]
            }
          />
          <Area
            type="monotone"
            dataKey="max"
            stroke="none"
            fill="url(#minMaxGrad)"
            fillOpacity={1}
          />
          <Area
            type="monotone"
            dataKey="min"
            stroke="none"
            fill="#ffffff"
            fillOpacity={1}
          />
          <Line
            type="monotone"
            dataKey="avg"
            stroke="#3b82f6"
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 4 }}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

function StatusDistributionChart({ data }: { data: MetricsBucket[] }) {
  if (data.length === 0) {
    return (
      <div className="rounded-lg border border-gray-200 bg-white p-5">
        <h3 className="mb-4 text-sm font-semibold text-gray-700">
          Status Distribution
        </h3>
        <div className="flex h-64 items-center justify-center text-sm text-gray-400">
          No data available for this period.
        </div>
      </div>
    );
  }

  const chartData = data.map((b) => ({
    time: formatChartTime(b.timestamp),
    healthy: b.healthy_count,
    degraded: b.degraded_count,
    down: b.down_count,
  }));

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-5">
      <h3 className="mb-4 text-sm font-semibold text-gray-700">
        Status Distribution
      </h3>
      <ResponsiveContainer width="100%" height={280}>
        <AreaChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
          <XAxis
            dataKey="time"
            tick={{ fontSize: 11, fill: "#9ca3af" }}
            tickLine={false}
          />
          <YAxis
            tick={{ fontSize: 11, fill: "#9ca3af" }}
            tickLine={false}
            axisLine={false}
          />
          <Tooltip
            contentStyle={{
              fontSize: 12,
              borderRadius: 8,
              border: "1px solid #e5e7eb",
            }}
          />
          <Area
            type="monotone"
            dataKey="healthy"
            stackId="1"
            stroke="#22c55e"
            fill="#22c55e"
            fillOpacity={0.6}
          />
          <Area
            type="monotone"
            dataKey="degraded"
            stackId="1"
            stroke="#eab308"
            fill="#eab308"
            fillOpacity={0.6}
          />
          <Area
            type="monotone"
            dataKey="down"
            stackId="1"
            stroke="#ef4444"
            fill="#ef4444"
            fillOpacity={0.6}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

function RegionStatusBreakdown({
  data,
}: {
  data: ByRegionResponse | null;
}) {
  if (!data || data.regions.length === 0) {
    return (
      <div className="rounded-lg border border-gray-200 bg-white p-5">
        <h3 className="mb-4 text-sm font-semibold text-gray-700">
          Region Status Breakdown
        </h3>
        <div className="py-8 text-center text-sm text-gray-400">
          No region data available. Configure check regions to enable
          multi-region monitoring.
        </div>
      </div>
    );
  }

  const consensusDot =
    STATUS_COLORS[data.consensus_status ?? ""] ?? "bg-gray-400";
  const consensusLabel =
    STATUS_LABELS[data.consensus_status ?? ""] ?? "Unknown";

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-5">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-gray-700">
          Region Status Breakdown
        </h3>
        <span className="flex items-center gap-1.5 text-xs text-gray-500">
          Consensus:
          <span
            className={`inline-block h-2 w-2 rounded-full ${consensusDot}`}
          />
          <span className="font-medium">{consensusLabel}</span>
        </span>
      </div>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {data.regions.map((r) => {
          const dot = STATUS_COLORS[r.status] ?? "bg-gray-400";
          const label = STATUS_LABELS[r.status] ?? "Unknown";
          return (
            <div
              key={r.region_id}
              className="rounded-lg border border-gray-100 bg-gray-50 p-3"
            >
              <div className="mb-1 flex items-center justify-between">
                <span className="text-sm font-medium text-gray-800">
                  {r.region_name}
                </span>
                <span className="flex items-center gap-1.5 text-xs">
                  <span
                    className={`inline-block h-2 w-2 rounded-full ${dot}`}
                  />
                  {label}
                </span>
              </div>
              <div className="flex gap-4 text-xs text-gray-500">
                <span>
                  {r.response_time_ms !== null
                    ? `${r.response_time_ms} ms`
                    : "N/A"}
                </span>
                {r.status_code !== null && <span>HTTP {r.status_code}</span>}
              </div>
              {r.error_message && (
                <p className="mt-1 truncate text-xs text-red-500">
                  {r.error_message}
                </p>
              )}
              <p className="mt-1 text-xs text-gray-400">
                {formatTime(r.checked_at)}
              </p>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function RecentChecksTable({ checks }: { checks: HealthCheck[] }) {
  if (checks.length === 0) {
    return (
      <div className="rounded-lg border border-gray-200 bg-white p-5">
        <h3 className="mb-4 text-sm font-semibold text-gray-700">
          Recent Checks
        </h3>
        <div className="py-8 text-center text-sm text-gray-400">
          No health checks recorded yet.
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-5">
      <h3 className="mb-4 text-sm font-semibold text-gray-700">
        Recent Checks
      </h3>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-100 text-left text-xs text-gray-500">
              <th className="pb-2 pr-4 font-medium">Status</th>
              <th className="pb-2 pr-4 font-medium">Response Time</th>
              <th className="pb-2 pr-4 font-medium">Status Code</th>
              <th className="pb-2 font-medium">Timestamp</th>
            </tr>
          </thead>
          <tbody>
            {checks.slice(0, 20).map((check) => {
              const dotColor =
                STATUS_COLORS[check.status] ?? "bg-gray-400";
              const label =
                STATUS_LABELS[check.status] ?? "Unknown";
              return (
                <tr
                  key={check.id}
                  className="border-b border-gray-50 last:border-0"
                >
                  <td className="py-2 pr-4">
                    <span className="flex items-center gap-1.5">
                      <span
                        className={`inline-block h-2 w-2 rounded-full ${dotColor}`}
                      />
                      {label}
                    </span>
                  </td>
                  <td className="py-2 pr-4 text-gray-600">
                    {check.response_time_ms !== null
                      ? `${check.response_time_ms} ms`
                      : "—"}
                  </td>
                  <td className="py-2 pr-4 text-gray-600">
                    {check.status_code ?? "—"}
                  </td>
                  <td className="py-2 text-gray-400">
                    {formatTime(check.checked_at)}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/* ---------- SSL Status ---------- */

function SSLStatusCard({ cert }: { cert: SSLCertificate | null }) {
  if (cert === null) {
    return (
      <div className="rounded-lg border border-gray-200 bg-white p-5">
        <h3 className="mb-4 text-sm font-semibold text-gray-700">
          SSL Certificate
        </h3>
        <div className="py-4 text-center text-sm text-gray-400">
          No SSL certificate data available. Service may not use HTTPS.
        </div>
      </div>
    );
  }

  const days = cert.days_until_expiry;
  let statusColor = "text-green-700 bg-green-100";
  let statusLabel = "Valid";
  if (days <= 7) {
    statusColor = "text-red-700 bg-red-100";
    statusLabel = "Critical";
  } else if (days <= 30) {
    statusColor = "text-yellow-700 bg-yellow-100";
    statusLabel = "Expiring Soon";
  }

  const expiryDate = new Date(cert.not_after).toLocaleDateString(undefined, {
    year: "numeric",
    month: "long",
    day: "numeric",
  });

  let dotColor = "bg-green-500";
  if (days <= 7) dotColor = "bg-red-500";
  else if (days <= 30) dotColor = "bg-yellow-500";

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-5">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-gray-700">SSL Certificate</h3>
        <span
          className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ${statusColor}`}
        >
          <span className={`inline-block h-1.5 w-1.5 rounded-full ${dotColor}`} />
          {statusLabel}
        </span>
      </div>
      <div className="space-y-3">
        <div className="flex items-start justify-between">
          <span className="text-xs text-gray-500">Issuer</span>
          <span className="max-w-[60%] text-right text-xs font-medium text-gray-700 break-all">
            {cert.issuer}
          </span>
        </div>
        <div className="flex items-start justify-between">
          <span className="text-xs text-gray-500">Subject</span>
          <span className="max-w-[60%] text-right text-xs font-medium text-gray-700 break-all">
            {cert.subject}
          </span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-xs text-gray-500">Expiry Date</span>
          <span className="text-xs font-medium text-gray-700">{expiryDate}</span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-xs text-gray-500">Days Remaining</span>
          <span className={`text-sm font-bold ${days <= 7 ? "text-red-600" : days <= 30 ? "text-yellow-600" : "text-green-600"}`}>
            {days}
          </span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-xs text-gray-500">Last Checked</span>
          <span className="text-xs text-gray-500">
            {new Date(cert.last_checked_at).toLocaleString()}
          </span>
        </div>
      </div>
    </div>
  );
}

/* ---------- Main page ---------- */

export default function ServiceDetail() {
  const { id } = useParams<{ id: string }>();

  const [service, setService] = useState<Service | null>(null);
  const [metrics, setMetrics] = useState<MetricsBucket[]>([]);
  const [uptime, setUptime] = useState<UptimePeriod[]>([]);
  const [checks, setChecks] = useState<HealthCheck[]>([]);
  const [sslCert, setSSLCert] = useState<SSLCertificate | null>(null);
  const [regionData, setRegionData] = useState<ByRegionResponse | null>(null);
  const [period, setPeriod] = useState<Period>("24h");
  const [loadingService, setLoadingService] = useState(true);
  const [loadingMetrics, setLoadingMetrics] = useState(true);
  const [loadingChecks, setLoadingChecks] = useState(true);
  const [loadingSSL, setLoadingSSL] = useState(true);
  const [loadingRegions, setLoadingRegions] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Load service info and uptime (once)
  useEffect(() => {
    if (!id) return;
    setLoadingService(true);
    Promise.all([fetchService(id), fetchUptime(id)])
      .then(([svc, upt]) => {
        setService(svc);
        setUptime(upt);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoadingService(false));
  }, [id]);

  // Load checks (once)
  useEffect(() => {
    if (!id) return;
    setLoadingChecks(true);
    fetchHealthChecks(id)
      .then(setChecks)
      .catch(() => {})
      .finally(() => setLoadingChecks(false));
  }, [id]);

  // Load SSL certificate info (once)
  useEffect(() => {
    if (!id) return;
    setLoadingSSL(true);
    fetchSSLCertificate(id)
      .then(setSSLCert)
      .catch(() => setSSLCert(null))
      .finally(() => setLoadingSSL(false));
  }, [id]);

  // Load region breakdown (once)
  useEffect(() => {
    if (!id) return;
    setLoadingRegions(true);
    fetchChecksByRegion(id)
      .then(setRegionData)
      .catch(() => setRegionData(null))
      .finally(() => setLoadingRegions(false));
  }, [id]);

  // Load metrics (on period change)
  const loadMetrics = useCallback(() => {
    if (!id) return;
    setLoadingMetrics(true);
    fetchMetrics(id, period)
      .then(setMetrics)
      .catch(() => setMetrics([]))
      .finally(() => setLoadingMetrics(false));
  }, [id, period]);

  useEffect(() => {
    loadMetrics();
  }, [loadMetrics]);

  const handlePeriodChange = (p: Period) => {
    setPeriod(p);
  };

  if (error) {
    return (
      <div className="mx-auto max-w-6xl px-4 py-8">
        <Link
          to="/"
          className="mb-4 inline-block text-sm text-blue-600 hover:underline"
        >
          &larr; Back to Dashboard
        </Link>
        <div className="rounded-lg border border-red-200 bg-red-50 p-6 text-center text-red-600">
          {error}
        </div>
      </div>
    );
  }

  // Determine current status from latest check
  const latestCheck = checks.length > 0 ? checks[0] : null;
  const currentStatus = latestCheck?.status ?? "unknown";
  const dotColor = STATUS_COLORS[currentStatus] ?? "bg-gray-400";
  const statusLabel = STATUS_LABELS[currentStatus] ?? "Unknown";

  // Get specific uptime values
  const uptime24h = uptime.find((u) => u.period === "24h");
  const uptime7d = uptime.find((u) => u.period === "7d");
  const uptime30d = uptime.find((u) => u.period === "30d");

  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      {/* Back link */}
      <Link
        to="/"
        className="mb-4 inline-block text-sm text-blue-600 hover:underline"
      >
        &larr; Back to Dashboard
      </Link>

      {/* Service header */}
      {loadingService ? (
        <div className="mb-6 rounded-lg border border-gray-200 bg-white p-6">
          <SkeletonBlock className="mb-2 h-7 w-48" />
          <SkeletonBlock className="mb-4 h-4 w-72" />
          <div className="flex gap-2">
            <SkeletonBlock className="h-6 w-24" />
            <SkeletonBlock className="h-6 w-24" />
            <SkeletonBlock className="h-6 w-24" />
          </div>
        </div>
      ) : service ? (
        <div className="mb-6 rounded-lg border border-gray-200 bg-white p-6">
          <div className="mb-2 flex items-center gap-3">
            <h1 className="text-2xl font-bold text-gray-900">
              {service.name}
            </h1>
            <span className="flex items-center gap-1.5 text-sm text-gray-600">
              <span
                className={`inline-block h-3 w-3 rounded-full ${dotColor}`}
              />
              {statusLabel}
            </span>
          </div>
          <p className="mb-4 text-sm text-gray-500">{service.url}</p>
          <div className="flex flex-wrap gap-2">
            <UptimeBadge
              period="24h"
              percentage={uptime24h?.uptime_percentage ?? null}
            />
            <UptimeBadge
              period="7d"
              percentage={uptime7d?.uptime_percentage ?? null}
            />
            <UptimeBadge
              period="30d"
              percentage={uptime30d?.uptime_percentage ?? null}
            />
          </div>
        </div>
      ) : null}

      {/* SSL Certificate Status */}
      {loadingSSL ? (
        <div className="mb-6">
          <div className="rounded-lg border border-gray-200 bg-white p-5">
            <SkeletonBlock className="mb-4 h-5 w-36" />
            <SkeletonBlock className="mb-2 h-4 w-full" />
            <SkeletonBlock className="mb-2 h-4 w-full" />
            <SkeletonBlock className="h-4 w-3/4" />
          </div>
        </div>
      ) : (
        <div className="mb-6">
          <SSLStatusCard cert={sslCert} />
        </div>
      )}

      {/* Period selector */}
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-800">Metrics</h2>
        <PeriodSelector selected={period} onChange={handlePeriodChange} />
      </div>

      {/* Charts */}
      <div className="mb-6 grid gap-6 lg:grid-cols-2">
        {loadingMetrics ? (
          <>
            <ChartSkeleton />
            <ChartSkeleton />
          </>
        ) : (
          <>
            <ResponseTimeChart data={metrics} />
            <StatusDistributionChart data={metrics} />
          </>
        )}
      </div>

      {/* Region status breakdown */}
      <div className="mb-6">
        {loadingRegions ? (
          <TableSkeleton />
        ) : (
          <RegionStatusBreakdown data={regionData} />
        )}
      </div>

      {/* Recent checks */}
      {loadingChecks ? <TableSkeleton /> : <RecentChecksTable checks={checks} />}
    </div>
  );
}
