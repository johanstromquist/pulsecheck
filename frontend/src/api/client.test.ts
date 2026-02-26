import { describe, it, expect, vi, beforeEach } from 'vitest';
import {
  fetchServices,
  createService,
  fetchService,
  fetchHealthChecks,
  fetchMetrics,
  fetchUptime,
  fetchSSLCertificate,
  fetchIncidents,
  fetchIncident,
  createIncident,
  resolveIncident,
  fetchStatusPage,
} from './client';

// Mock global fetch
const mockFetch = vi.fn();
global.fetch = mockFetch;

describe('API Client', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('fetchServices', () => {
    it('fetches services successfully', async () => {
      const mockData = [{ id: '1', name: 'test' }];
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(mockData),
      });

      const result = await fetchServices();
      expect(result).toEqual(mockData);
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/v1/services?limit=100&offset=0'),
      );
    });

    it('throws on error response', async () => {
      mockFetch.mockResolvedValue({
        ok: false,
        statusText: 'Internal Server Error',
      });

      await expect(fetchServices()).rejects.toThrow('Failed to fetch services');
    });
  });

  describe('createService', () => {
    it('creates a service successfully', async () => {
      const payload = { name: 'New Service', url: 'https://example.com' };
      const mockResponse = { id: '1', ...payload };
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(mockResponse),
      });

      const result = await createService(payload);
      expect(result).toEqual(mockResponse);
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/v1/services'),
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify(payload),
        }),
      );
    });
  });

  describe('fetchService', () => {
    it('fetches a single service', async () => {
      const mockData = { id: '1', name: 'test' };
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(mockData),
      });

      const result = await fetchService('1');
      expect(result).toEqual(mockData);
    });
  });

  describe('fetchHealthChecks', () => {
    it('fetches health checks for a service', async () => {
      const mockData = [{ id: '1', status: 'healthy' }];
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(mockData),
      });

      const result = await fetchHealthChecks('service-1');
      expect(result).toEqual(mockData);
    });
  });

  describe('fetchMetrics', () => {
    it('fetches metrics with default period', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve([]),
      });

      await fetchMetrics('service-1');
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('period=24h'),
      );
    });

    it('fetches metrics with custom period', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve([]),
      });

      await fetchMetrics('service-1', '7d');
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('period=7d'),
      );
    });
  });

  describe('fetchUptime', () => {
    it('fetches uptime data', async () => {
      const mockData = [{ period: '24h', uptime_percentage: 99.9 }];
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(mockData),
      });

      const result = await fetchUptime('service-1');
      expect(result).toEqual(mockData);
    });
  });

  describe('fetchSSLCertificate', () => {
    it('returns null for 404', async () => {
      mockFetch.mockResolvedValue({
        ok: false,
        status: 404,
      });

      const result = await fetchSSLCertificate('service-1');
      expect(result).toBeNull();
    });

    it('returns certificate data', async () => {
      const mockData = { id: '1', days_until_expiry: 30 };
      mockFetch.mockResolvedValue({
        ok: true,
        status: 200,
        json: () => Promise.resolve(mockData),
      });

      const result = await fetchSSLCertificate('service-1');
      expect(result).toEqual(mockData);
    });
  });

  describe('fetchIncidents', () => {
    it('fetches incidents without filters', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve([]),
      });

      await fetchIncidents();
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/v1/incidents'),
      );
    });

    it('fetches incidents with status filter', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve([]),
      });

      await fetchIncidents({ status: 'investigating' });
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('status=investigating'),
      );
    });
  });

  describe('fetchIncident', () => {
    it('fetches a single incident', async () => {
      const mockData = { id: '1', title: 'test', updates: [] };
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(mockData),
      });

      const result = await fetchIncident('1');
      expect(result).toEqual(mockData);
    });
  });

  describe('createIncident', () => {
    it('creates an incident', async () => {
      const payload = { title: 'Outage', severity: 'critical' as const };
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ id: '1', ...payload }),
      });

      const result = await createIncident(payload);
      expect(result.title).toBe('Outage');
    });
  });

  describe('resolveIncident', () => {
    it('resolves an incident', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ id: '1', status: 'resolved' }),
      });

      const result = await resolveIncident('1');
      expect(result.status).toBe('resolved');
    });
  });

  describe('fetchStatusPage', () => {
    it('fetches status page data', async () => {
      const mockData = {
        overall_status: 'operational',
        services: [],
        active_incidents: [],
        recent_incidents: [],
      };
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(mockData),
      });

      const result = await fetchStatusPage();
      expect(result.overall_status).toBe('operational');
    });
  });
});
