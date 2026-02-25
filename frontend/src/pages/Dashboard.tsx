import { useEffect, useState, useCallback } from "react";
import type { Service, HealthCheck } from "../api/client";
import { fetchServices } from "../api/client";
import ServiceCard from "../components/ServiceCard";
import AddServiceModal from "../components/AddServiceModal";
import { useWebSocket } from "../hooks/useWebSocket";
import type { HealthCheckMessage } from "../hooks/useWebSocket";

const REFRESH_INTERVAL = 30_000;

export default function Dashboard() {
  const [services, setServices] = useState<Service[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [latestChecks, setLatestChecks] = useState<
    Record<string, HealthCheckMessage>
  >({});

  const handleWsMessage = useCallback((msg: HealthCheckMessage) => {
    if (msg.type === "health_check") {
      setLatestChecks((prev) => ({ ...prev, [msg.service_id]: msg }));
    }
  }, []);

  const { connected } = useWebSocket(handleWsMessage);

  const loadServices = useCallback(async () => {
    try {
      const data = await fetchServices();
      setServices(data);
    } catch {
      // keep existing data on refresh failure
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadServices();
    const id = window.setInterval(loadServices, REFRESH_INTERVAL);
    return () => window.clearInterval(id);
  }, [loadServices]);

  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      <div className="mb-6 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-bold text-gray-900">PulseCheck</h1>
          <span
            className="flex items-center gap-1.5 text-xs text-gray-500"
            title={connected ? "Live updates active" : "Reconnecting…"}
          >
            <span
              className={`inline-block h-2 w-2 rounded-full ${
                connected ? "bg-green-500" : "bg-red-500"
              }`}
            />
            {connected ? "Live" : "Disconnected"}
          </span>
        </div>
        <button
          onClick={() => setModalOpen(true)}
          className="rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
        >
          + Add Service
        </button>
      </div>

      {loading ? (
        <p className="text-gray-500">Loading services…</p>
      ) : services.length === 0 ? (
        <p className="text-gray-500">
          No services yet. Click "+ Add Service" to get started.
        </p>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {services.map((service) => (
            <ServiceCard
              key={service.id}
              service={service}
              realtimeCheck={latestChecks[service.id] ?? null}
            />
          ))}
        </div>
      )}

      <AddServiceModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        onCreated={loadServices}
      />
    </div>
  );
}
