import { useEffect, useState, useCallback } from "react";
import { Link } from "react-router-dom";
import type {
  Incident,
  IncidentSeverity,
  IncidentStatusType,
  CreateIncidentPayload,
  Service,
} from "../api/client";
import { fetchIncidents, createIncident, fetchServices } from "../api/client";

const SEVERITY_COLORS: Record<IncidentSeverity, string> = {
  minor: "bg-yellow-100 text-yellow-800",
  major: "bg-orange-100 text-orange-800",
  critical: "bg-red-100 text-red-800",
};

const STATUS_COLORS: Record<IncidentStatusType, string> = {
  investigating: "bg-red-100 text-red-800",
  identified: "bg-orange-100 text-orange-800",
  monitoring: "bg-blue-100 text-blue-800",
  resolved: "bg-green-100 text-green-800",
};

function formatTime(iso: string): string {
  return new Date(iso).toLocaleString();
}

function Badge({ text, colorClass }: { text: string; colorClass: string }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium capitalize ${colorClass}`}
    >
      {text}
    </span>
  );
}

function CreateIncidentModal({
  open,
  onClose,
  onCreated,
  services,
}: {
  open: boolean;
  onClose: () => void;
  onCreated: () => void;
  services: Service[];
}) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [severity, setSeverity] = useState<IncidentSeverity>("major");
  const [selectedServices, setSelectedServices] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!open) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const payload: CreateIncidentPayload = {
        title,
        description: description || undefined,
        severity,
        affected_service_ids: selectedServices,
        created_by: "user",
      };
      await createIncident(payload);
      setTitle("");
      setDescription("");
      setSeverity("major");
      setSelectedServices([]);
      onCreated();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create incident");
    } finally {
      setLoading(false);
    }
  };

  const toggleService = (id: string) => {
    setSelectedServices((prev) =>
      prev.includes(id) ? prev.filter((s) => s !== id) : [...prev, id],
    );
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="w-full max-w-lg rounded-lg bg-white p-6 shadow-xl">
        <h2 className="mb-4 text-lg font-bold text-gray-900">
          Create Incident
        </h2>
        {error && (
          <div className="mb-3 rounded bg-red-50 p-2 text-sm text-red-600">
            {error}
          </div>
        )}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">
              Title
            </label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              required
              className="w-full rounded border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">
              Description
            </label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
              className="w-full rounded border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">
              Severity
            </label>
            <select
              value={severity}
              onChange={(e) => setSeverity(e.target.value as IncidentSeverity)}
              className="w-full rounded border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
            >
              <option value="minor">Minor</option>
              <option value="major">Major</option>
              <option value="critical">Critical</option>
            </select>
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">
              Affected Services
            </label>
            <div className="max-h-32 space-y-1 overflow-y-auto rounded border border-gray-200 p-2">
              {services.length === 0 ? (
                <p className="text-xs text-gray-400">No services available</p>
              ) : (
                services.map((svc) => (
                  <label
                    key={svc.id}
                    className="flex items-center gap-2 text-sm"
                  >
                    <input
                      type="checkbox"
                      checked={selectedServices.includes(svc.id)}
                      onChange={() => toggleService(svc.id)}
                    />
                    {svc.name}
                  </label>
                ))
              )}
            </div>
          </div>
          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded px-4 py-2 text-sm text-gray-600 hover:bg-gray-100"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading || !title}
              className="rounded bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50"
            >
              {loading ? "Creating..." : "Create Incident"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function IncidentList() {
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [services, setServices] = useState<Service[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [filter, setFilter] = useState<"all" | "open" | "resolved">("all");

  const loadIncidents = useCallback(async () => {
    try {
      const data = await fetchIncidents({ limit: 100 });
      setIncidents(data);
    } catch {
      // keep existing data
    } finally {
      setLoading(false);
    }
  }, []);

  const loadServices = useCallback(async () => {
    try {
      const data = await fetchServices();
      setServices(data);
    } catch {
      // ignore
    }
  }, []);

  useEffect(() => {
    loadIncidents();
    loadServices();
  }, [loadIncidents, loadServices]);

  const filteredIncidents = incidents.filter((inc) => {
    if (filter === "open") return inc.status !== "resolved";
    if (filter === "resolved") return inc.status === "resolved";
    return true;
  });

  const openCount = incidents.filter((i) => i.status !== "resolved").length;

  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Incidents</h1>
          {openCount > 0 && (
            <p className="mt-1 text-sm text-red-600">
              {openCount} open incident{openCount !== 1 ? "s" : ""}
            </p>
          )}
        </div>
        <div className="flex items-center gap-3">
          <Link
            to="/"
            className="text-sm text-blue-600 hover:underline"
          >
            Dashboard
          </Link>
          <Link
            to="/status"
            className="text-sm text-blue-600 hover:underline"
          >
            Status Page
          </Link>
          <button
            onClick={() => setModalOpen(true)}
            className="rounded bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700"
          >
            + New Incident
          </button>
        </div>
      </div>

      {/* Filter tabs */}
      <div className="mb-4 flex gap-1">
        {(["all", "open", "resolved"] as const).map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`rounded px-3 py-1.5 text-xs font-medium capitalize transition-colors ${
              filter === f
                ? "bg-gray-900 text-white"
                : "bg-gray-100 text-gray-600 hover:bg-gray-200"
            }`}
          >
            {f}
          </button>
        ))}
      </div>

      {loading ? (
        <p className="text-gray-500">Loading incidents...</p>
      ) : filteredIncidents.length === 0 ? (
        <div className="rounded-lg border border-gray-200 bg-white p-8 text-center text-gray-400">
          No incidents found.
        </div>
      ) : (
        <div className="space-y-3">
          {filteredIncidents.map((incident) => (
            <Link
              key={incident.id}
              to={`/incidents/${incident.id}`}
              className="block rounded-lg border border-gray-200 bg-white p-4 transition hover:border-gray-300 hover:shadow-sm"
            >
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="mb-1 flex items-center gap-2">
                    <h3 className="font-semibold text-gray-900">
                      {incident.title}
                    </h3>
                    <Badge
                      text={incident.severity}
                      colorClass={SEVERITY_COLORS[incident.severity]}
                    />
                    <Badge
                      text={incident.status}
                      colorClass={STATUS_COLORS[incident.status]}
                    />
                  </div>
                  {incident.description && (
                    <p className="mb-2 text-sm text-gray-500 line-clamp-1">
                      {incident.description}
                    </p>
                  )}
                  <div className="flex items-center gap-4 text-xs text-gray-400">
                    <span>Started: {formatTime(incident.started_at)}</span>
                    {incident.resolved_at && (
                      <span>
                        Resolved: {formatTime(incident.resolved_at)}
                      </span>
                    )}
                    <span>By: {incident.created_by}</span>
                  </div>
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}

      <CreateIncidentModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        onCreated={loadIncidents}
        services={services}
      />
    </div>
  );
}
