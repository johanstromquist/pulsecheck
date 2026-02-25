import { useEffect, useState, useCallback } from "react";
import { useParams, Link } from "react-router-dom";
import type {
  IncidentDetail as IncidentDetailType,
  IncidentStatusType,
  CreateIncidentUpdatePayload,
  Service,
} from "../api/client";
import {
  fetchIncident,
  addIncidentUpdate,
  resolveIncident,
  fetchServices,
} from "../api/client";

const SEVERITY_COLORS: Record<string, string> = {
  minor: "bg-yellow-100 text-yellow-800",
  major: "bg-orange-100 text-orange-800",
  critical: "bg-red-100 text-red-800",
};

const STATUS_COLORS: Record<string, string> = {
  investigating: "bg-red-100 text-red-800",
  identified: "bg-orange-100 text-orange-800",
  monitoring: "bg-blue-100 text-blue-800",
  resolved: "bg-green-100 text-green-800",
};

const STATUS_DOT_COLORS: Record<string, string> = {
  investigating: "bg-red-500",
  identified: "bg-orange-500",
  monitoring: "bg-blue-500",
  resolved: "bg-green-500",
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

export default function IncidentDetail() {
  const { id } = useParams<{ id: string }>();
  const [incident, setIncident] = useState<IncidentDetailType | null>(null);
  const [services, setServices] = useState<Service[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Update form
  const [message, setMessage] = useState("");
  const [updateStatus, setUpdateStatus] =
    useState<IncidentStatusType>("investigating");
  const [submitting, setSubmitting] = useState(false);

  // Resolve confirmation
  const [showResolveConfirm, setShowResolveConfirm] = useState(false);
  const [resolving, setResolving] = useState(false);

  const loadIncident = useCallback(async () => {
    if (!id) return;
    try {
      const data = await fetchIncident(id);
      setIncident(data);
      setUpdateStatus(data.status);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load incident");
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    loadIncident();
    fetchServices()
      .then(setServices)
      .catch(() => {});
  }, [loadIncident]);

  const handleAddUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!id || !message.trim()) return;
    setSubmitting(true);
    try {
      const payload: CreateIncidentUpdatePayload = {
        message: message.trim(),
        status: updateStatus,
        created_by: "user",
      };
      await addIncidentUpdate(id, payload);
      setMessage("");
      await loadIncident();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to add update",
      );
    } finally {
      setSubmitting(false);
    }
  };

  const handleResolve = async () => {
    if (!id) return;
    setResolving(true);
    try {
      await resolveIncident(id);
      setShowResolveConfirm(false);
      await loadIncident();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to resolve incident",
      );
    } finally {
      setResolving(false);
    }
  };

  const getServiceName = (serviceId: string) => {
    const svc = services.find((s) => s.id === serviceId);
    return svc?.name ?? serviceId.slice(0, 8) + "...";
  };

  if (error && !incident) {
    return (
      <div className="mx-auto max-w-4xl px-4 py-8">
        <Link
          to="/incidents"
          className="mb-4 inline-block text-sm text-blue-600 hover:underline"
        >
          &larr; Back to Incidents
        </Link>
        <div className="rounded-lg border border-red-200 bg-red-50 p-6 text-center text-red-600">
          {error}
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="mx-auto max-w-4xl px-4 py-8">
        <Link
          to="/incidents"
          className="mb-4 inline-block text-sm text-blue-600 hover:underline"
        >
          &larr; Back to Incidents
        </Link>
        <p className="text-gray-500">Loading incident...</p>
      </div>
    );
  }

  if (!incident) return null;

  const isResolved = incident.status === "resolved";

  return (
    <div className="mx-auto max-w-4xl px-4 py-8">
      <Link
        to="/incidents"
        className="mb-4 inline-block text-sm text-blue-600 hover:underline"
      >
        &larr; Back to Incidents
      </Link>

      {error && (
        <div className="mb-4 rounded bg-red-50 p-2 text-sm text-red-600">
          {error}
        </div>
      )}

      {/* Incident header */}
      <div className="mb-6 rounded-lg border border-gray-200 bg-white p-6">
        <div className="mb-3 flex items-start justify-between">
          <div>
            <div className="mb-2 flex items-center gap-2">
              <h1 className="text-xl font-bold text-gray-900">
                {incident.title}
              </h1>
              <Badge
                text={incident.severity}
                colorClass={SEVERITY_COLORS[incident.severity] ?? ""}
              />
              <Badge
                text={incident.status}
                colorClass={STATUS_COLORS[incident.status] ?? ""}
              />
            </div>
            {incident.description && (
              <p className="mb-3 text-sm text-gray-600">
                {incident.description}
              </p>
            )}
          </div>
          {!isResolved && (
            <button
              onClick={() => setShowResolveConfirm(true)}
              className="rounded bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-700"
            >
              Resolve
            </button>
          )}
        </div>

        {/* Affected services */}
        {incident.affected_service_ids.length > 0 && (
          <div className="mb-3">
            <span className="text-xs font-medium text-gray-500">
              Affected Services:
            </span>
            <div className="mt-1 flex flex-wrap gap-1">
              {incident.affected_service_ids.map((sid) => (
                <span
                  key={sid}
                  className="rounded bg-gray-100 px-2 py-0.5 text-xs text-gray-700"
                >
                  {getServiceName(sid)}
                </span>
              ))}
            </div>
          </div>
        )}

        <div className="flex gap-4 text-xs text-gray-400">
          <span>Started: {formatTime(incident.started_at)}</span>
          {incident.resolved_at && (
            <span>Resolved: {formatTime(incident.resolved_at)}</span>
          )}
          <span>Created by: {incident.created_by}</span>
        </div>
      </div>

      {/* Timeline */}
      <div className="mb-6">
        <h2 className="mb-4 text-lg font-semibold text-gray-800">Timeline</h2>
        {incident.updates.length === 0 ? (
          <div className="rounded-lg border border-gray-200 bg-white p-6 text-center text-sm text-gray-400">
            No updates yet.
          </div>
        ) : (
          <div className="space-y-0">
            {incident.updates.map((update, idx) => (
              <div key={update.id} className="relative flex gap-4">
                {/* Timeline line */}
                <div className="flex flex-col items-center">
                  <div
                    className={`h-3 w-3 rounded-full ${STATUS_DOT_COLORS[update.status] ?? "bg-gray-400"}`}
                  />
                  {idx < incident.updates.length - 1 && (
                    <div className="w-0.5 flex-1 bg-gray-200" />
                  )}
                </div>
                {/* Content */}
                <div className="mb-4 flex-1 rounded-lg border border-gray-200 bg-white p-4">
                  <div className="mb-1 flex items-center gap-2">
                    <Badge
                      text={update.status}
                      colorClass={STATUS_COLORS[update.status] ?? ""}
                    />
                    <span className="text-xs text-gray-400">
                      {formatTime(update.created_at)}
                    </span>
                    <span className="text-xs text-gray-400">
                      by {update.created_by}
                    </span>
                  </div>
                  <p className="text-sm text-gray-700">{update.message}</p>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Add update form */}
      {!isResolved && (
        <div className="rounded-lg border border-gray-200 bg-white p-6">
          <h3 className="mb-3 text-sm font-semibold text-gray-700">
            Post Update
          </h3>
          <form onSubmit={handleAddUpdate} className="space-y-3">
            <textarea
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              placeholder="Describe the update..."
              rows={3}
              required
              className="w-full rounded border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
            />
            <div className="flex items-center gap-3">
              <select
                value={updateStatus}
                onChange={(e) =>
                  setUpdateStatus(e.target.value as IncidentStatusType)
                }
                className="rounded border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
              >
                <option value="investigating">Investigating</option>
                <option value="identified">Identified</option>
                <option value="monitoring">Monitoring</option>
                <option value="resolved">Resolved</option>
              </select>
              <button
                type="submit"
                disabled={submitting || !message.trim()}
                className="rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
              >
                {submitting ? "Posting..." : "Post Update"}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Resolve confirmation dialog */}
      {showResolveConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="w-full max-w-sm rounded-lg bg-white p-6 shadow-xl">
            <h3 className="mb-2 text-lg font-bold text-gray-900">
              Resolve Incident?
            </h3>
            <p className="mb-4 text-sm text-gray-600">
              This will mark the incident as resolved and set the resolution
              time. This action cannot be undone.
            </p>
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setShowResolveConfirm(false)}
                className="rounded px-4 py-2 text-sm text-gray-600 hover:bg-gray-100"
              >
                Cancel
              </button>
              <button
                onClick={handleResolve}
                disabled={resolving}
                className="rounded bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-700 disabled:opacity-50"
              >
                {resolving ? "Resolving..." : "Resolve"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
